"""Tiny client for IntaSend's hosted checkout.

Two calls only: create a checkout page and read an invoice's state.
Money lands in the IntaSend wallet, which pays out to the bank account
connected in the IntaSend dashboard.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT = 20


class IntaSendError(Exception):
    pass


def is_configured():
    return bool(
        settings.INTAASEND_PUBLISHABLE_KEY and settings.INTAASEND_SECRET_KEY
    )


def create_checkout(amount, email, invoice_id, api_ref, redirect_url):
    """Return {'url': <hosted page>, 'invoice_id': ...}. Raises IntaSendError."""
    if not is_configured():
        raise IntaSendError("IntaSend keys are not set")

    payload = {
        "currency": "KES",
        "amount": str(amount),
        "email": email,
        "invoice_id": invoice_id,
        "api_ref": api_ref,
        "host": settings.FRONTEND_URL,
        "redirect_url": redirect_url,
        "comment": "YasTalk Premium",
    }
    try:
        r = requests.post(
            f"{settings.INTAASEND_API_BASE}/api/v1/checkout/",
            json=payload,
            headers={
                "X-IntaSend-Public-API-Key": settings.INTAASEND_PUBLISHABLE_KEY,
                "Content-Type": "application/json",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as exc:
        logger.exception("IntaSend checkout request failed")
        raise IntaSendError("Could not start the IntaSend checkout") from exc

    invoice = data.get("invoice") or {}
    url = data.get("url") or invoice.get("payment_link") or ""
    if not url:
        raise IntaSendError("IntaSend did not return a checkout link")
    return {"url": url, "invoice_id": invoice.get("invoice_id") or invoice_id}


def invoice_state(invoice_id):
    """Ask IntaSend for the truth. Returns (STATE, invoice dict); ('', {}) on failure.

    Never trust the webhook body alone: anyone who learns the challenge string
    could post a fake 'COMPLETE'. The state API is the source of truth.
    """
    if not (settings.INTAASEND_SECRET_KEY and invoice_id):
        return "", {}
    try:
        r = requests.get(
            f"{settings.INTAASEND_API_BASE}/api/v1/payment/status/",
            params={"invoice_id": invoice_id},
            headers={"Authorization": f"Bearer {settings.INTAASEND_SECRET_KEY}"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json() or {}
    except (requests.RequestException, ValueError):
        logger.exception("IntaSend status check failed for %s", invoice_id)
        return "", {}

    invoice = data.get("invoice") or {}
    return str(invoice.get("state") or "").upper(), invoice
