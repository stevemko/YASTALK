import base64
import logging
from datetime import datetime

import requests
from decouple import config
from django.core.cache import cache

logger = logging.getLogger(__name__)

ENV = config("MPESA_ENV", default="sandbox")
BASE = "https://sandbox.safaricom.co.ke" if ENV == "sandbox" else "https://api.safaricom.co.ke"


def _get_token():
    token = cache.get("mpesa_token")
    if token:
        return token
    r = requests.get(
        f"{BASE}/oauth/v1/generate?grant_type=client_credentials",
        auth=(config("MPESA_CONSUMER_KEY"), config("MPESA_CONSUMER_SECRET")),
        timeout=15,
    )
    r.raise_for_status()
    token = r.json()["access_token"]
    cache.set("mpesa_token", token, 3000)    # token lasts 1 hour; refresh a bit early
    return token


def stk_push(phone, amount, reference):
    shortcode = config("MPESA_SHORTCODE")
    passkey = config("MPESA_PASSKEY")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",   # use "CustomerBuyGoodsOnline" if you use a Till number
        "Amount": int(amount),
        "PartyA": phone,
        "PartyB": shortcode,
        "PhoneNumber": phone,
        "CallBackURL": config("MPESA_CALLBACK_URL"),
        "AccountReference": reference[:12],
        "TransactionDesc": "YasTalk payment",
    }
    r = requests.post(
        f"{BASE}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers={"Authorization": f"Bearer {_get_token()}"},
        timeout=20,
    )
    if r.status_code == 401:               # token expired early: clear and retry once
        cache.delete("mpesa_token")
        r = requests.post(
            f"{BASE}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {_get_token()}"},
            timeout=20,
        )
    if not r.ok:
        logger.error("STK push failed: %s %s", r.status_code, r.text)
    r.raise_for_status()
    return r.json()