import hmac
import logging
import re
import threading
from datetime import timedelta

from decouple import config
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

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


def normalize_phone(raw):
    """Turn 0712345678 / +254712345678 / 712345678 into 254712345678, or None if invalid."""
    p = re.sub(r"\D", "", raw or "")
    if p.startswith("0"):
        p = "254" + p[1:]
    elif p[:1] in ("7", "1"):
        p = "254" + p
    return p if re.fullmatch(r"254[17]\d{8}", p) else None


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


class PaymentInitiateThrottle(AnonRateThrottle):
    # Own scope, so status polling and other public calls
    # don't use up this limit (the default anon scope is shared)
    scope = "payment_initiate"
    rate = "5/min"


class InitiatePayment(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PaymentInitiateThrottle]

    def post(self, request):
        plan = request.data.get("plan")
        email = (request.data.get("email") or "").strip()
        phone = normalize_phone(request.data.get("phone"))

        if plan not in PLANS:
            return Response({"error": "Unknown plan"}, status=400)
        if not phone:
            return Response({"error": "Enter a valid Safaricom number, e.g. 0712345678"}, status=400)
        if not email:
            return Response({"error": "Email is required"}, status=400)

        # Stop double payments: a pending request for the same phone+plan in the last 2 minutes
        recent = Payment.objects.filter(
            phone=phone, plan=plan, status=Payment.Status.PENDING,
            created_at__gte=timezone.now() - timedelta(minutes=2),
        ).first()
        if recent:
            return Response(
                {"payment_id": str(recent.id), "message": "A prompt was already sent. Check your phone."},
                status=409,
            )

        pay = Payment.objects.create(email=email, phone=phone, plan=plan, amount=PLANS[plan])

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
    """Called by Safaricom after the customer pays or cancels."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def post(self, request, secret):
        # Safaricom doesn't sign callbacks, so the URL itself carries a secret.
        # Compare as bytes so odd characters in the URL can't cause a 500 error.
        if not hmac.compare_digest(secret.encode(), config("MPESA_CALLBACK_SECRET").encode()):
            return Response(status=404)

        cb = (request.data.get("Body") or {}).get("stkCallback") or {}
        pay = Payment.objects.filter(checkout_request_id=cb.get("CheckoutRequestID")).first()

        if pay and pay.status == Payment.Status.PENDING:
            pay.result_desc = str(cb.get("ResultDesc", ""))[:200]

            if cb.get("ResultCode") == 0:
                items = {
                    i.get("Name"): i.get("Value")
                    for i in (cb.get("CallbackMetadata") or {}).get("Item", [])
                }
                paid_amount = items.get("Amount")
                if paid_amount is not None and int(float(paid_amount)) != pay.amount:
                    logger.warning(
                        "Payment %s: expected KSh %s but M-Pesa reports KSh %s",
                        pay.id, pay.amount, paid_amount,
                    )

                pay.status = Payment.Status.SUCCESS
                pay.mpesa_receipt = str(items.get("MpesaReceiptNumber", ""))
                pay.paid_at = timezone.now()
                pay.save()
                logger.info("Payment %s succeeded (%s)", pay.id, pay.mpesa_receipt)
                _send_receipt_email(pay)
            else:
                pay.status = Payment.Status.FAILED
                pay.save()
                logger.info("Payment %s failed: %s", pay.id, pay.result_desc)

        return Response({"ResultCode": 0, "ResultDesc": "Accepted"})


class PaymentStatus(APIView):
    """The frontend polls this every few seconds after the M-Pesa prompt is sent."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        pay = Payment.objects.filter(pk=pk).first()
        if not pay:
            return Response({"status": "not_found"}, status=404)
        return Response({
            "status": pay.status,
            "receipt": pay.mpesa_receipt if pay.status == Payment.Status.SUCCESS else "",
            "message": pay.result_desc if pay.status == Payment.Status.FAILED else "",
        })
