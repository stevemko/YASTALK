import hmac
import logging
import threading
from datetime import timedelta

from decouple import config
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .auth_serializers import is_email_verified, normalize_phone
from .models import Payment
from .mpesa import stk_push

logger = logging.getLogger(__name__)

# IMPORTANT: replace with YOUR real plan names and prices (KSh).
# These are placeholders. The server decides the price, never the browser,
# and the plan keys must match the ones your frontend sends.
PLANS = {
    "mini": 499,
    "basic": 699,
    "standard": 999,
    "premium": 1699,
}


def _send_receipt_email(pay):
    """Send the confirmation email in the background so Safaricom's callback is answered fast."""
    def _send():
        try:
            send_mail(
                "YasTalk payment received",
                f"Thank you! We received your payment of KSh {pay.amount} "
                f"for the {pay.plan} plan.\n\nM-Pesa receipt: {pay.mpesa_receipt}",
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
            user=user, email=user.email, phone=phone, plan=plan, amount=PLANS[plan]
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
                    .filter(checkout_request_id=checkout_id)
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
                        logger.info("Payment %s succeeded (%s)", pay.id, pay.mpesa_receipt)
                        send_receipt = pay
                    else:
                        pay.status = Payment.Status.FAILED
                        pay.save()
                        logger.info("Payment %s failed: %s", pay.id, pay.result_desc)

            if send_receipt:
                _send_receipt_email(send_receipt)

        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


class PaymentStatus(APIView):
    """The frontend polls this every few seconds after the M-Pesa prompt is sent.
    Only the account that made the payment can see it."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        pay = Payment.objects.filter(pk=pk, user=request.user).first()
        if not pay:
            return Response({"status": "not_found"}, status=404)
        return Response({
            "status": pay.status,
            "receipt": pay.mpesa_receipt if pay.status == Payment.Status.SUCCESS else "",
            "message": pay.result_desc if pay.status == Payment.Status.FAILED else "",
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
                "status": p.status,
                "receipt": p.mpesa_receipt if p.status == Payment.Status.SUCCESS else "",
                "created_at": p.created_at,
                "paid_at": p.paid_at,
            }
            for p in rows
        ])