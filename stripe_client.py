"""
Tactify — Stripe payment client
Uses raw httpx calls with Basic auth (secret key as username, empty password).
No stripe-py SDK required, though stripe package may be installed.
"""

import os
from typing import Optional

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

_STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
_STRIPE_PRO_PRICE_ID = os.environ.get("STRIPE_PRO_PRICE_ID", "")
_STRIPE_CLUB_PRICE_ID = os.environ.get("STRIPE_CLUB_PRICE_ID", "")

_STRIPE_BASE = "https://api.stripe.com/v1"

# Plan definitions
PLANS = {
    "pro": {
        "name": "Pro",
        "price": "£9.99/mo",
        "price_id_env": "STRIPE_PRO_PRICE_ID",
    },
    "club": {
        "name": "Club",
        "price": "£49/mo",
        "price_id_env": "STRIPE_CLUB_PRICE_ID",
    },
}


def _is_configured() -> bool:
    return bool(_STRIPE_SECRET_KEY and _HTTPX_AVAILABLE)


def _auth() -> tuple:
    """Basic auth tuple: (secret_key, empty_password)."""
    return (_STRIPE_SECRET_KEY, "")


def _price_id_for_plan(plan: str) -> str:
    """Return the Stripe price ID for the given plan slug."""
    if plan == "pro":
        return _STRIPE_PRO_PRICE_ID
    elif plan == "club":
        return _STRIPE_CLUB_PRICE_ID
    return ""


def create_checkout_session(
    email: str,
    plan: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout session and return the checkout URL.

    Returns empty string if Stripe is not configured or on error.

    plan options: 'pro' (£9.99/mo), 'club' (£49/mo)
    success_url should include {CHECKOUT_SESSION_ID} placeholder so we can
    verify on redirect back.
    """
    if not _is_configured():
        return ""

    price_id = _price_id_for_plan(plan)
    if not price_id:
        return ""

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{_STRIPE_BASE}/checkout/sessions",
                auth=_auth(),
                data={
                    "mode": "subscription",
                    "customer_email": email,
                    "line_items[0][price]": price_id,
                    "line_items[0][quantity]": "1",
                    "success_url": success_url,
                    "cancel_url": cancel_url,
                    "allow_promotion_codes": "true",
                },
            )
            resp.raise_for_status()
            session = resp.json()
            return session.get("url", "")
    except Exception:
        return ""


def verify_checkout_session(session_id: str) -> Optional[dict]:
    """Retrieve a Checkout session by ID.

    Returns {email, status, customer_id, subscription_id} if the session
    is paid/complete, None otherwise.
    """
    if not _is_configured() or not session_id:
        return None

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                f"{_STRIPE_BASE}/checkout/sessions/{session_id}",
                auth=_auth(),
                params={"expand[]": "subscription"},
            )
            resp.raise_for_status()
            session = resp.json()

            payment_status = session.get("payment_status", "")
            status = session.get("status", "")

            # Accept 'paid' payment_status or 'complete' status
            if payment_status not in ("paid",) and status not in ("complete",):
                return None

            customer_email = session.get("customer_email") or session.get(
                "customer_details", {}
            ).get("email", "")

            subscription = session.get("subscription")
            subscription_id = None
            if isinstance(subscription, dict):
                subscription_id = subscription.get("id")
            elif isinstance(subscription, str):
                subscription_id = subscription

            return {
                "email": customer_email,
                "status": payment_status or status,
                "customer_id": session.get("customer"),
                "subscription_id": subscription_id,
            }
    except Exception:
        return None


def get_subscription_status(customer_id: str) -> str:
    """Return the subscription status for a Stripe customer.

    Returns: 'active', 'cancelled', or 'none'.
    """
    if not _is_configured() or not customer_id:
        return "none"

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                f"{_STRIPE_BASE}/subscriptions",
                auth=_auth(),
                params={
                    "customer": customer_id,
                    "limit": "1",
                    "status": "all",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            subs = data.get("data", [])
            if not subs:
                return "none"

            sub_status = subs[0].get("status", "")
            if sub_status == "active":
                return "active"
            if sub_status in ("canceled", "cancelled", "unpaid", "past_due"):
                return "cancelled"
            return "none"
    except Exception:
        return "none"


def create_customer_portal_session(customer_id: str, return_url: str) -> str:
    """Create a Stripe Customer Portal session and return its URL.

    Returns empty string if Stripe is not configured or on error.
    """
    if not _is_configured() or not customer_id:
        return ""

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{_STRIPE_BASE}/billing_portal/sessions",
                auth=_auth(),
                data={
                    "customer": customer_id,
                    "return_url": return_url,
                },
            )
            resp.raise_for_status()
            portal = resp.json()
            return portal.get("url", "")
    except Exception:
        return ""
