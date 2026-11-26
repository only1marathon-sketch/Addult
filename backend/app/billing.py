"""Credit purchases via a high-risk payment processor (e.g. CCBill, Segpay, Verotel).

Mainstream processors (Stripe, PayPal) generally prohibit explicit content.
Each processor signs its webhooks differently. Replace `verify_and_parse` with
your processor's documented verification before going live.
"""

import hashlib
import hmac
import json

from .config import settings

# Map your processor's product/price IDs to credit amounts.
PACKAGES = {"credits_50": 50, "credits_200": 200, "credits_1000": 1000}


def verify_and_parse(signature: str | None, body: bytes) -> tuple[int, int] | None:
    """Generic HMAC-SHA256 check. Returns (user_id, credits) or None if invalid.

    Expected JSON body: {"user_id": 123, "package": "credits_50", "status": "approved"}
    """
    if not settings.billing_webhook_secret or not signature:
        return None
    expected = hmac.new(settings.billing_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    data = json.loads(body)
    if data.get("status") != "approved" or data.get("package") not in PACKAGES:
        return None
    return int(data["user_id"]), PACKAGES[data["package"]]
