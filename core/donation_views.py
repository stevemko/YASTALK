"""Donations: M-Pesa prompt, card (Paystack hosted checkout) and crypto (BEP-20, confirmed by hand).

Anyone may donate without an account, so these endpoints are public. That makes the limits
below important: they stop the form being used to spam someone's phone or to test stolen cards.
"""
import hashlib
import hmac
import json
import logging
import re
import threading
import uuid
from datetime import timedelta

import requests
from decouple import config
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .auth_serializers import normalize_phone
from .models import Donation
from .mpesa import stk_push

logger = logging.getLogger(__name__)

PRESETS = [200, 500, 1000, 2500, 5000]      # amount buttons on the donate page (KSh)
MIN_AMOUNT, MAX_AMOUNT = 20, 150000         # 150,000 is M-Pesa's per-transaction limit
PAYSTACK_API = 'https://api.paystack.co'
TX_HASH = re.compile(r'^0x[a-fA-F0-9]{64}$')
EVM_ADDRESS = re.compile(r'^0x[a-fA-F0-9]{40}$')


# ---------------------------------------------------------------- helpers
def _mpesa_ready():
    keys = ('MPESA_CONSUMER_KEY', 'MPESA_CONSUMER_SECRET', 'MPESA_SHORTCODE',
            'MPESA_PASSKEY', 'MPESA_CALLBACK_URL', 'MPESA_CALLBACK_SECRET')
    return all(config(k, default='') for k in keys)


def _parse_amount(value):
    try:
        amount = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return amount if MIN_AMOUNT <= amount <= MAX_AMOUNT else None


def _amount_error():
    return {'error': f'Enter an amount between KSh {MIN_AMOUNT:,} and KSh {MAX_AMOUNT:,}.'}


def _donor_fields(data):
    """Optional details a donor may add. Returns (fields, error)."""
    email = str(data.get('email') or '').strip()[:254]
    if email:
        try:
            validate_email(email)
        except ValidationError:
            return None, 'That email address does not look right.'
    return {
        'donor_name': str(data.get('name') or '').strip()[:120],
        'donor_email': email,
        'message': str(data.get('message') or '').strip()[:280],
        'is_anonymous': bool(data.get('anonymous')),
    }, None


def _thank(don):
    """Email a thank-you in the background so the person is never kept waiting."""
    if not don.donor_email:
        return

    def _send():
        try:
            if don.method == Donation.Method.CRYPTO:
                body = ("Thank you for supporting YasTalk! We have received your note about your "
                        "crypto transfer and will confirm it once we have checked it on the blockchain.")
            else:
                body = (f"Thank you for supporting YasTalk! We received your gift of KSh {don.amount:,}."
                        + (f"\n\nM-Pesa receipt: {don.mpesa_receipt}" if don.mpesa_receipt else ""))
            send_mail("Thank you for supporting YasTalk", body, None, [don.donor_email], fail_silently=True)
        except Exception:
            logger.exception("Could not send thank-you email for donation %s", don.id)

    threading.Thread(target=_send, daemon=True).start()


class _PublicDonationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []        # a stale login token must never break a public form
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'donate'


# ---------------------------------------------------------------- config
class DonationConfig(APIView):
    """GET /api/donations/config/ -- which ways to give are switched on. The website shows only these."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        address = (settings.DONATION_BEP20_ADDRESS or '').strip()
        crypto = None
        if EVM_ADDRESS.match(address):      # never show a mistyped address
            crypto = {
                'address': address,
                'network': 'BNB Smart Chain (BEP-20)',
                'tokens': [t.strip() for t in settings.DONATION_CRYPTO_TOKENS.split(',') if t.strip()],
            }
        paybill = None
        if settings.DONATION_PAYBILL:
            paybill = {'number': settings.DONATION_PAYBILL, 'account': settings.DONATION_PAYBILL_ACCOUNT}
        return Response({
            'currency': 'KES',
            'presets': PRESETS,
            'min_amount': MIN_AMOUNT,
            'max_amount': MAX_AMOUNT,
            'methods': {
                'mpesa': _mpesa_ready(),
                'paybill': bool(paybill),
                'card': bool(settings.PAYSTACK_SECRET_KEY),
                'crypto': bool(crypto),
            },
            'paybill': paybill,
            'crypto': crypto,
        })


# ---------------------------------------------------------------- M-Pesa prompt
class DonateMpesa(_PublicDonationView):
    """POST {amount, phone, name?, email?, message?, anonymous?} -> sends an M-Pesa prompt."""

    def post(self, request):
        if not _mpesa_ready():
            return Response({'error': 'M-Pesa donations are not switched on yet.'}, status=503)

        amount = _parse_amount(request.data.get('amount'))
        if amount is None:
            return Response(_amount_error(), status=400)
        phone = normalize_phone(request.data.get('phone'))
        if not phone:
            return Response({'error': 'Enter a valid Safaricom number, e.g. 0712345678'}, status=400)
        fields, err = _donor_fields(request.data)
        if err:
            return Response({'error': err}, status=400)

        now = timezone.now()
        # A prompt is already out for this number: carry on with it instead of sending another.
        recent = Donation.objects.filter(
            phone=phone, method=Donation.Method.MPESA, status=Donation.Status.PENDING,
            created_at__gte=now - timedelta(minutes=2),
        ).first()
        if recent:
            return Response({'donation_id': str(recent.id),
                             'message': 'A prompt was already sent. Check your phone.'}, status=409)
        # Stop the form being used to pester one phone with prompts.
        if Donation.objects.filter(phone=phone, created_at__gte=now - timedelta(hours=1)).count() >= 3:
            return Response({'error': 'Too many attempts for this number. Please try again in an hour.'},
                            status=429)

        don = Donation.objects.create(method=Donation.Method.MPESA, amount=amount, phone=phone, **fields)
        try:
            res = stk_push(phone, amount, 'YasTalk gift')
        except Exception:
            logger.exception('STK push error for donation %s', don.id)
            don.status = Donation.Status.FAILED
            don.result_desc = 'Could not reach M-Pesa'
            don.save(update_fields=['status', 'result_desc'])
            return Response({'error': 'Could not reach M-Pesa. Please try again.'}, status=502)

        if res.get('ResponseCode') != '0':
            don.status = Donation.Status.FAILED
            don.result_desc = str(res.get('ResponseDescription', ''))[:200]
            don.save(update_fields=['status', 'result_desc'])
            return Response({'error': 'M-Pesa rejected the request. Check your number.'}, status=400)

        don.provider_ref = res.get('CheckoutRequestID', '')
        don.save(update_fields=['provider_ref'])
        return Response({'donation_id': str(don.id), 'message': 'Check your phone and enter your M-Pesa PIN.'})


def settle_mpesa_donation(checkout_id, cb):
    """Called by the shared M-Pesa callback. Returns True if this id belonged to a donation."""
    thank = None
    with transaction.atomic():
        don = (Donation.objects.select_for_update()
               .filter(method=Donation.Method.MPESA, provider_ref=checkout_id).first())
        if not don:
            return False
        if don.status == Donation.Status.PENDING:
            don.result_desc = str(cb.get('ResultDesc', ''))[:200]
            if cb.get('ResultCode') == 0:
                items = {i.get('Name'): i.get('Value')
                         for i in (cb.get('CallbackMetadata') or {}).get('Item', [])}
                don.status = Donation.Status.SUCCESS
                don.mpesa_receipt = str(items.get('MpesaReceiptNumber', ''))
                don.paid_at = timezone.now()
                thank = don
            else:
                don.status = Donation.Status.FAILED
            don.save()
            logger.info('Donation %s -> %s', don.id, don.status)
    if thank:
        _thank(thank)
    return True


class DonationStatus(_PublicDonationView):
    """GET /api/donations/<uuid>/status/ -- polled by the page after the prompt. No personal details."""
    throttle_scope = 'donate_status'

    def get(self, request, pk):
        don = Donation.objects.filter(pk=pk).first()
        if not don:
            return Response({'status': 'not_found'}, status=404)
        return Response({
            'status': don.status,
            'receipt': don.mpesa_receipt if don.status == Donation.Status.SUCCESS else '',
            'message': don.result_desc if don.status == Donation.Status.FAILED else '',
        })


# ---------------------------------------------------------------- card (Paystack)
def _paystack_headers():
    return {'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'}


def _settle_card(don_id, data):
    """Apply a Paystack result (from verify or webhook). Safe to run twice."""
    thank = None
    with transaction.atomic():
        don = Donation.objects.select_for_update().get(pk=don_id)
        if don.status != Donation.Status.PENDING:
            return don
        outcome = data.get('status')
        if outcome == 'success':
            paid_ok = int(data.get('amount') or 0) == (don.amount or 0) * 100
            currency_ok = (data.get('currency') or 'KES') == 'KES'
            if paid_ok and currency_ok:
                don.status = Donation.Status.SUCCESS
                don.paid_at = timezone.now()
                thank = don
            else:
                # Money arrived but not in the amount we asked for: leave it for a human to look at.
                don.result_desc = 'Paid amount differs from the request: check Paystack'
                logger.error('Donation %s: Paystack reports %s %s, expected KES %s',
                             don.id, data.get('currency'), data.get('amount'), don.amount)
            don.save()
        elif outcome == 'failed':
            don.status = Donation.Status.FAILED
            don.result_desc = str(data.get('gateway_response', ''))[:200]
            don.save()
    if thank:
        _thank(thank)
    return Donation.objects.get(pk=don_id)


class DonateCard(_PublicDonationView):
    """POST {amount, email, name?, message?, anonymous?} -> {authorization_url} to send the donor to."""

    def post(self, request):
        if not settings.PAYSTACK_SECRET_KEY:
            return Response({'error': 'Card donations are not switched on yet.'}, status=503)
        amount = _parse_amount(request.data.get('amount'))
        if amount is None:
            return Response(_amount_error(), status=400)
        fields, err = _donor_fields(request.data)
        if err:
            return Response({'error': err}, status=400)
        if not fields['donor_email']:
            return Response({'error': 'Enter your email so the card payment page can send your receipt.'},
                            status=400)

        reference = f'yasdon_{uuid.uuid4().hex[:20]}'
        don = Donation.objects.create(method=Donation.Method.CARD, amount=amount,
                                      provider_ref=reference, **fields)
        try:
            res = requests.post(
                f'{PAYSTACK_API}/transaction/initialize',
                headers=_paystack_headers(), timeout=15,
                json={
                    'email': fields['donor_email'],
                    'amount': amount * 100,                 # Paystack wants the smallest unit (cents)
                    'currency': 'KES',
                    'reference': reference,
                    'callback_url': f'{settings.FRONTEND_URL}/donate/thanks?reference={reference}',
                    'metadata': {'donation_id': str(don.id), 'purpose': 'donation'},
                },
            )
            body = res.json()
            url = (body.get('data') or {}).get('authorization_url')
            if not body.get('status') or not url:
                raise ValueError(body.get('message', 'no authorization url'))
        except Exception:
            logger.exception('Paystack initialize failed for donation %s', don.id)
            don.status = Donation.Status.FAILED
            don.result_desc = 'Could not start the card payment'
            don.save(update_fields=['status', 'result_desc'])
            return Response({'error': 'Could not open the card payment page. Please try again.'}, status=502)

        return Response({'authorization_url': url, 'reference': reference})


class VerifyCard(_PublicDonationView):
    """GET /api/donations/card/verify/?reference=... -- the page asks this when the donor comes back."""
    throttle_scope = 'donate_status'

    def get(self, request):
        reference = str(request.query_params.get('reference') or '')[:100]
        don = Donation.objects.filter(method=Donation.Method.CARD, provider_ref=reference).first()
        if not don:
            return Response({'status': 'not_found'}, status=404)
        if don.status == Donation.Status.PENDING and settings.PAYSTACK_SECRET_KEY:
            try:
                res = requests.get(f'{PAYSTACK_API}/transaction/verify/{reference}',
                                   headers=_paystack_headers(), timeout=15)
                data = (res.json() or {}).get('data') or {}
                don = _settle_card(don.pk, data)
            except Exception:
                logger.exception('Paystack verify failed for %s', reference)   # still pending: try again
        return Response({'status': don.status, 'amount': don.amount})


class PaystackWebhook(APIView):
    """Paystack tells us about every payment, even if the donor closed the tab. Signed, so it cannot be faked."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def post(self, request):
        key = settings.PAYSTACK_SECRET_KEY
        if not key:
            return Response(status=404)
        raw = request.body
        expected = hmac.new(key.encode(), raw, hashlib.sha512).hexdigest()
        given = request.headers.get('x-paystack-signature', '')
        if not hmac.compare_digest(expected, given):
            return Response(status=401)

        try:
            event = json.loads(raw)
        except ValueError:
            return Response(status=400)
        data = event.get('data') or {}
        if event.get('event') == 'charge.success':
            don = Donation.objects.filter(method=Donation.Method.CARD,
                                          provider_ref=data.get('reference', '')).first()
            if don:
                _settle_card(don.pk, data)
        return Response({'ok': True})


# ---------------------------------------------------------------- crypto (BEP-20)
class DonateCrypto(_PublicDonationView):
    """POST {tx_hash, name?, email?, message?, anonymous?} -- a donor tells us they sent crypto.
    We cannot see the blockchain from here, so this records it as pending and you confirm it
    in the admin after checking the hash on bscscan.com."""

    def post(self, request):
        tx = str(request.data.get('tx_hash') or '').strip()
        if not TX_HASH.match(tx):
            return Response({'error': 'That does not look like a transaction hash. '
                                      'It starts with 0x and is 66 characters long.'}, status=400)
        fields, err = _donor_fields(request.data)
        if err:
            return Response({'error': err}, status=400)

        existing = Donation.objects.filter(method=Donation.Method.CRYPTO, tx_hash__iexact=tx).first()
        if existing:
            return Response({'detail': 'Thank you! We already have this transaction and will confirm it soon.'})

        don = Donation.objects.create(method=Donation.Method.CRYPTO, tx_hash=tx, **fields)
        _thank(don)
        return Response({'detail': 'Thank you! We will confirm your transfer once we have checked it.'})
