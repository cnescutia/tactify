"""
Tactify — Supabase REST API client
Uses raw httpx calls (no supabase-py SDK) so it works in HuggingFace Spaces
without heavy dependencies.
"""

import os
from typing import Optional

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

FREE_ANALYSIS_LIMIT = 1


def _headers() -> dict:
    return {
        "apikey": _SUPABASE_KEY,
        "Authorization": f"Bearer {_SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _is_configured() -> bool:
    return bool(_SUPABASE_URL and _SUPABASE_KEY and _HTTPX_AVAILABLE)


def _table_url(table: str) -> str:
    return f"{_SUPABASE_URL.rstrip('/')}/rest/v1/{table}"


def get_or_create_user(email: str) -> dict:
    """Upsert user record, return {id, email, analyses_used, is_pro,
    stripe_customer_id, created_at}. Fails open if Supabase unreachable."""
    if not _is_configured():
        return _default_user(email)

    try:
        with httpx.Client(timeout=10.0) as client:
            # Try to fetch existing user first
            resp = client.get(
                _table_url("users"),
                headers=_headers(),
                params={"email": f"eq.{email}", "select": "*"},
            )
            resp.raise_for_status()
            rows = resp.json()

            if rows:
                return rows[0]

            # User doesn't exist — create
            create_resp = client.post(
                _table_url("users"),
                headers=_headers(),
                json={"email": email, "analyses_used": 0, "is_pro": False},
            )
            create_resp.raise_for_status()
            created = create_resp.json()
            if isinstance(created, list) and created:
                return created[0]
            return _default_user(email)

    except Exception:
        return _default_user(email)


def get_user(email: str) -> Optional[dict]:
    """Fetch user by email. Returns None if not found or Supabase unreachable."""
    if not _is_configured():
        return None

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                _table_url("users"),
                headers=_headers(),
                params={"email": f"eq.{email}", "select": "*"},
            )
            resp.raise_for_status()
            rows = resp.json()
            return rows[0] if rows else None
    except Exception:
        return None


def increment_analyses(email: str) -> int:
    """Increment analyses_used for user, return new count.
    Returns -1 if Supabase unreachable (fail open)."""
    if not _is_configured():
        return -1

    try:
        with httpx.Client(timeout=10.0) as client:
            # Fetch current count first
            resp = client.get(
                _table_url("users"),
                headers=_headers(),
                params={"email": f"eq.{email}", "select": "analyses_used"},
            )
            resp.raise_for_status()
            rows = resp.json()
            current = rows[0].get("analyses_used", 0) if rows else 0
            new_count = current + 1

            # Update
            update_resp = client.patch(
                _table_url("users"),
                headers=_headers(),
                params={"email": f"eq.{email}"},
                json={"analyses_used": new_count},
            )
            update_resp.raise_for_status()
            return new_count
    except Exception:
        return -1


def set_pro(email: str, stripe_customer_id: str, stripe_subscription_id: str) -> bool:
    """Mark user as Pro in Supabase. Returns True on success."""
    if not _is_configured():
        return False

    try:
        from datetime import datetime, timezone
        with httpx.Client(timeout=10.0) as client:
            resp = client.patch(
                _table_url("users"),
                headers=_headers(),
                params={"email": f"eq.{email}"},
                json={
                    "is_pro": True,
                    "stripe_customer_id": stripe_customer_id,
                    "stripe_subscription_id": stripe_subscription_id,
                    "pro_since": datetime.now(timezone.utc).isoformat(),
                },
            )
            resp.raise_for_status()
            return True
    except Exception:
        return False


def check_can_analyze(email: str) -> tuple:
    """Returns (can_analyze: bool, reason: str).
    Free tier: 1 analysis. Pro: unlimited.
    Fails open — returns (True, '') if Supabase unreachable."""
    if not _is_configured():
        return (True, "")

    try:
        user = get_user(email)
        if user is None:
            # New user — create and allow
            get_or_create_user(email)
            return (True, "")

        if user.get("is_pro", False):
            return (True, "")

        analyses_used = user.get("analyses_used", 0)
        if analyses_used < FREE_ANALYSIS_LIMIT:
            return (True, "")

        return (
            False,
            f"You have used your {FREE_ANALYSIS_LIMIT} free "
            f"{'analysis' if FREE_ANALYSIS_LIMIT == 1 else 'analyses'}. "
            "Upgrade to Pro for unlimited analyses.",
        )
    except Exception:
        # Fail open — never block the user due to our infra issues
        return (True, "")


def _default_user(email: str) -> dict:
    """Return a sensible default user dict when Supabase is unavailable."""
    return {
        "id": None,
        "email": email,
        "analyses_used": 0,
        "is_pro": False,
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "created_at": None,
        "pro_since": None,
    }
