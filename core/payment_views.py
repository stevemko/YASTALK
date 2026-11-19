import hmac
import logging
import threading
from datetime import timedelta

from decouple import config
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .auth_serializers import is_email_verified, normalize_phone
from . import intasend
from .intasend import IntaSendError, invoice_state
from .models import Payment
from .mpesa import stk_push
from .subscriptions import extend_subscription, subscription_payload

logger = logging.getLogger(__name__)

# These are the only two plans in the app. The server decides the price,
# never the browser, and the keys must match the ones the frontend sends.
PLANS = {
    "free": 0,
    "premium": settings.PREMIUM_PRICE_KES,
}
PLAN_USD = {
    "free": "0.00",
    "premium": str(settings.PREMIUM_PRICE_USD),
}


def _receipt_reference(pay):
    return pay.mpesa_receipt or pay.invoice_id or str(pay.id)


def _send_receipt_email(pay):
    """Send the confirmation email in the background so the webhook is answered fast."""
    def _send():
        try:
            send_mail(
                "YasTalk payment received",
                f"Thank you! We received your payment of KSh {pay.amount} "
                f"for the {pay.plan} plan.\n\nReference: {_receipt_reference(pay)}\n"
                f"Your plan is active for {settings.SUBSCRIPTION_DAYS} days from today.",
                None,
                [pay.email],
                fail_silently=True,
            )
        except Exception:
            logger.exception("Could not send receipt email for payment %s", pay.id)

    threading.Thread(target=_send, daemon=True).start()


class PaymentInitiateThrottle(UserRateThrottle):
    # Per logged-in user, on its own scope so status polling and other calls
    # don't use up this limit.
    scope = "payment_initiate"
    rate = "5/min"


class PlansView(APIView):
    """GET /api/payments/plans/ — the plans and the prices the server will charge."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({
            "plans": [
                {"key": key, "amount": amount, "usd": PLAN_USD[key]}
                for key, amount in PLANS.items()
            ],
            "currency": "KES",
            "billing": "monthly",
            "subscription_days": settings.SUBSCRIPTION_DAYS,
            "checkout": "intasend",
        })


def settle_intasend_payment(invoice_id, state, payload=None, invoice=None):
    """Move a pending IntaSend payment to its final state. Safe to call twice:
    the row is locked and anything no longer pending is left alone."""
    invoice = invoice or {}
    payload = payload or {}
    receipt = None

    with transaction.atomic():
        pay = (
            Payment.objects.select_for_update()
            .filter(invoice_id=invoice_id, provider=Payment.Provider.INTASEND)
            .first()
        )
        if not pay or pay.status != Payment.Status.PENDING:
            return pay

        if state == "COMPLETE":
            paid = invoice.get("value", payload.get("value"))
            try:
                paid = float(paid)
            except (TypeError, ValueError):
                paid = None
            if paid is not None and abs(paid - pay.amount) > 1:
                logger.warning(
                    "Payment %s: expected KSh %s but IntaSend reports %s",
                    pay.id, pay.amount, paid,
                )

            pay.status = Payment.Status.SUCCESS
            pay.mpesa_receipt = str(
                invoice.get("provider_ref")
                or invoice.get("mpesa_reference")
                or payload.get("provider_ref")
                or ""
            )[:30]
            pay.paid_at = timezone.now()
            pay.save()
            if pay.user_id:
                extend_subscription(pay.user, pay.plan)
            logger.info("IntaSend payment %s succeeded (invoice %s)", pay.id, invoice_id)
            receipt = pay

        elif state == "FAILED":
            pay.status = Payment.Status.FAILED
            pay.result_desc = str(
                invoice.get("failed_reason")
                or payload.get("failed_reason")
                or "Payment did not go through"
            )[:200]
            pay.save()
            logger.info("IntaSend payment %s failed: %s", pay.id, pay.result_desc)

    if receipt:
        _send_receipt_email(receipt)
    return pay


class IntaSendCheckout(APIView):
    """POST {plan} -> returns the IntaSend hosted checkout link. Needs a logged-in account."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [PaymentInitiateThrottle]

    def post(self, request):
        user = request.user
        plan = request.data.get("plan")

        if not is_email_verified(user):
            return Response(
                {
                    "error": "Please confirm your email before paying. Open your Account page "
                             "to get a new confirmation link.",
                    "code": "email_not_verified",
                },
                status=403,
            )
        if plan not in PLANS:
            return Response({"error": "Unknown plan"}, status=400)
        if PLANS[plan] <= 0:
            return Response(
                {"error": "Freemium is free and already available. Choose Premium to subscribe."},
                status=400,
            )
        if not settings.INTAASEND_PUBLISHABLE_KEY or not settings.INTAASEND_SECRET_KEY:
            return Response(
                {"error": "Card and M-Pesa checkout is being set up. Please try again later."},
                status=503,
            )

        pay = Payment.objects.create(
            user=user,
            email=user.email,
            plan=plan,
            amount=PLANS[plan],
            provider=Payment.Provider.INTASEND,
        )

        try:
            result = intasend.create_checkout(
                amount=pay.amount,
                email=user.email,
                invoice_id=str(pay.id),
                api_ref=f"yastalk-{plan}",
                redirect_url=f"{settings.FRONTEND_URL}/pricing?payment={pay.id}",
            )
        except IntaSendError:
            pay.status = Payment.Status.FAILED
            pay.result_desc = "Could not start IntaSend checkout"
            pay.save(update_fields=["status", "result_desc"])
            return Response(
                {"error": "Could not open the checkout page. Please try again in a moment."},
                status=502,
            )

        pay.invoice_id = result["invoice_id"]
        pay.save(update_fields=["invoice_id"])
        return Response({
            "payment_id": str(pay.id),
            "checkout_url": result["url"],
        })


class IntaSendWebhook(APIView):
    """Called by IntaSend when a payment changes state. Public, but every
    callback is re-checked against IntaSend's status API before we trust it."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def post(self, request):
        expected = settings.INTAASEND_WEBHOOK_CHALLENGE
        body = request.data if isinstance(request.data, dict) else {}
        event = body.get("collection_event")
        if not isinstance(event, dict):
            event = body

        challenge = str(event.get("challenge") or body.get("challenge") or "")
        if not expected or not hmac.compare_digest(challenge.encode(), str(expected).encode()):
            logger.warning("IntaSend webhook with a wrong challenge")
            return Response({"detail": "Invalid challenge"}, status=403)

        invoice_id = str(event.get("invoice_id") or "")
        if not invoice_id:
            return Response({"detail": "Missing invoice_id"}, status=400)

        state, invoice = invoice_state(invoice_id)
        if not state:
            # Can't verify right now; answer 200 so IntaSend doesn't hammer us
            # and let the status poll / a retry settle it.
            logger.warning("IntaSend webhook could not verify invoice %s", invoice_id)
            return Response({"status": "deferred"})

        settle_intasend_payment(invoice_id, state, event, invoice)
        return Response({"status": "ok"})


class InitiatePayment(APIView):
    """POST {plan, phone?} -> sends an M-Pesa prompt. Needs a logged-in account."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [PaymentInitiateThrottle]

    def post(self, request):
        user = request.user
        plan = request.data.get("plan")

        # Money only moves for accounts whose email we have confirmed, so receipts
        # and password recovery always reach a real inbox.
        if not is_email_verified(user):
            return Response(
                {
                    "error": "Please confirm your email before paying. Open your Account page "
                             "to get a new confirmation link.",
                    "code": "email_not_verified",
                },
                status=403,
            )

        # The M-Pesa number can differ from the account phone; fall back to the profile phone
        raw_phone = request.data.get("phone") or getattr(getattr(user, "profile", None), "phone", "")
        phone = normalize_phone(raw_phone)

        if plan not in PLANS:
            return Response({"error": "Unknown plan"}, status=400)
        if PLANS[plan] <= 0:
            return Response(
                {"error": "The Freemium plan is free and already available. Choose a paid plan to subscribe."},
                status=400,
            )
        if not phone:
            return Response({"error": "Enter a valid Safaricom number, e.g. 0712345678"}, status=400)
        if not user.email:
            return Response({"error": "Your account has no email address"}, status=400)

        # Stop double payments: a pending request for the same account+plan in the last 2 minutes
        recent = Payment.objects.filter(
            user=user, plan=plan, status=Payment.Status.PENDING,
            created_at__gte=timezone.now() - timedelta(minutes=2),
        ).first()
        if recent:
            return Response(
                {"payment_id": str(recent.id), "message": "A prompt was already sent. Check your phone."},
                status=409,
            )

        # Email always comes from the account, never from the request
        pay = Payment.objects.create(
            user=user, email=user.email, phone=phone, plan=plan, amount=PLANS[plan],
            provider=Payment.Provider.MPESA,
        )

        try:
            res = stk_push(phone, pay.amount, str(pay.id))
        except Exception:
            logger.exception("STK push error for payment %s", pay.id)
            pay.status = Payment.Status.FAILED
            pay.result_desc = "Could not reach M-Pesa"
            pay.save(update_fields=["status", "result_desc"])
            return Response({"error": "Could not reach M-Pesa. Please try again."}, status=502)

        if res.get("ResponseCode") != "0":
            pay.status = Payment.Status.FAILED
            pay.result_desc = str(res.get("ResponseDescription", ""))[:200]
            pay.save(update_fields=["status", "result_desc"])
            return Response({"error": "M-Pesa rejected the request. Check your number."}, status=400)

        pay.checkout_request_id = res.get("CheckoutRequestID", "")
        pay.save(update_fields=["checkout_request_id"])
        return Response({
            "payment_id": str(pay.id),
            "message": "Check your phone and enter your M-Pesa PIN.",
        })


class MpesaCallback(APIView):
    """Called by Safaricom after the customer pays or cancels. Must stay public."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def post(self, request, secret):
        # Safaricom doesn't sign callbacks, so the URL itself carries a secret.
        # Compare as bytes so odd characters in the URL can't cause a 500 error.
        expected = config("MPESA_CALLBACK_SECRET", default="")
        if not expected or not hmac.compare_digest(secret.encode(), expected.encode()):
            return Response(status=404)

        cb = (request.data.get("Body") or {}).get("stkCallback") or {}
        checkout_id = cb.get("CheckoutRequestID")
        send_receipt = None

        if checkout_id:
            # Lock the row so a duplicate callback can't mark it successful twice
            with transaction.atomic():
                pay = (
                    Payment.objects.select_for_update()
                    .filter(
                        checkout_request_id=checkout_id,
                        provider=Payment.Provider.MPESA,
                    )
                    .first()
                )

                if pay and pay.status == Payment.Status.PENDING:
                    pay.result_desc = str(cb.get("ResultDesc", ""))[:200]

                    if cb.get("ResultCode") == 0:
                        items = {
                            i.get("Name"): i.get("Value")
                            for i in (cb.get("CallbackMetadata") or {}).get("Item", [])
                        }
                        try:
                            paid_amount = int(float(items.get("Amount")))
                        except (TypeError, ValueError):
                            paid_amount = None
                        if paid_amount is not None and paid_amount != pay.amount:
                            logger.warning(
                                "Payment %s: expected KSh %s but M-Pesa reports KSh %s",
                                pay.id, pay.amount, paid_amount,
                            )

                        pay.status = Payment.Status.SUCCESS
                        pay.mpesa_receipt = str(items.get("MpesaReceiptNumber", ""))
                        pay.paid_at = timezone.now()
                        pay.save()
                        # A successful plan payment also extends the account's subscription.
                        if pay.user_id:
                            extend_subscription(pay.user, pay.plan)
                        logger.info("Payment %s succeeded (%s)", pay.id, pay.mpesa_receipt)
                        send_receipt = pay
                    else:
                        pay.status = Payment.Status.FAILED
                        pay.save()
                        logger.info("Payment %s failed: %s", pay.id, pay.result_desc)
                elif not pay:
                    # The same callback also settles public donation prompts.
                    from .donation_views import settle_mpesa_donation
                    settle_mpesa_donation(checkout_id, cb)

            if send_receipt:
                _send_receipt_email(send_receipt)

        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


class PaymentStatus(APIView):
    """The frontend polls this after coming back from IntaSend.
    Only the account that made the payment can see it."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        pay = Payment.objects.filter(pk=pk, user=request.user).first()
        if not pay:
            return Response({"status": "not_found"}, status=404)

        # Webhooks can be slow or lost; ask IntaSend directly while pending.
        if (
            pay.status == Payment.Status.PENDING
            and pay.provider == Payment.Provider.INTASEND
            and pay.invoice_id
        ):
            state, invoice = invoice_state(pay.invoice_id)
            if state:
                pay = settle_intasend_payment(pay.invoice_id, state, {}, invoice) or pay

        sub = subscription_payload(pay.user) if pay.user_id else None
        return Response({
            "status": pay.status,
            "plan": pay.plan,
            "receipt": _receipt_reference(pay) if pay.status == Payment.Status.SUCCESS else "",
            "message": pay.result_desc if pay.status == Payment.Status.FAILED else "",
            "subscription": sub,
        })


class PaymentHistory(APIView):
    """GET /api/payments/ — the logged-in account's own payments, newest first."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = Payment.objects.filter(user=request.user)[:50]
        return Response([
            {
                "id": str(p.id),
                "plan": p.plan,
                "amount": p.amount,
                "provider": p.provider,
                "status": p.status,
                "receipt": _receipt_reference(p) if p.status == Payment.Status.SUCCESS else "",
                "created_at": p.created_at,
                "paid_at": p.paid_at,
            }
            for p in rows
        ])