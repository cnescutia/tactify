"""
Tactify — Simple email-based auth layer for Streamlit.
No passwords, no magic links — just an email gate to identify users
and gate the paywall. Works on HuggingFace Spaces.
"""

import re
from typing import Optional

import streamlit as st

from db_client import get_or_create_user, set_pro
from stripe_client import create_checkout_session, verify_checkout_session, PLANS

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_SESSION_KEY = "user_email"
_JUST_UPGRADED_KEY = "_tactify_just_upgraded"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


def _current_url() -> str:
    """Best-effort URL of the running Streamlit app."""
    try:
        # Streamlit 1.30+ exposes this
        return st.query_params.get("_base_url", "http://localhost:8501")
    except Exception:
        return "http://localhost:8501"


def _success_url() -> str:
    base = _current_url().rstrip("/")
    return f"{base}/?session_id={{CHECKOUT_SESSION_ID}}"


def _cancel_url() -> str:
    return _current_url()


# ── Auth gate ─────────────────────────────────────────────────────────────────

def render_auth_gate() -> Optional[str]:
    """Render the email input UI in the sidebar.

    Returns the email string if the user has entered one, None otherwise.
    Stores the email in st.session_state['user_email'].
    """
    with st.sidebar:
        # If already signed in, show badge + switch link
        existing_email = st.session_state.get(_SESSION_KEY, "")

        if existing_email and _valid_email(existing_email):
            st.markdown(
                f"""
                <div style="background:#00FF8715;border:1px solid #00FF8740;
                            border-radius:8px;padding:10px 14px;margin-bottom:8px;">
                    <div style="color:#00FF87;font-size:11px;font-weight:700;
                                letter-spacing:1px;">Signed in as</div>
                    <div style="color:#fff;font-size:12px;word-break:break-all;
                                margin-top:2px;">{existing_email}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                "Switch account",
                key="_auth_switch",
                use_container_width=False,
                help="Sign in with a different email",
            ):
                st.session_state[_SESSION_KEY] = ""
                st.rerun()

            st.markdown(
                '<hr style="border-color:#1a1a1a;margin:12px 0;">',
                unsafe_allow_html=True,
            )
            return existing_email

        # Not yet signed in — show email form
        st.markdown(
            """
            <div style="color:#fff;font-size:14px;font-weight:700;
                        letter-spacing:-0.3px;margin-bottom:4px;">
                Get Started
            </div>
            <div style="color:#555;font-size:11px;margin-bottom:12px;">
                Enter your email to save your analyses and unlock Pro features.
            </div>
            """,
            unsafe_allow_html=True,
        )

        email_input = st.text_input(
            "Email address",
            key="_auth_email_input",
            placeholder="coach@example.com",
            label_visibility="collapsed",
        )

        col_btn, _ = st.columns([2, 1])
        with col_btn:
            continue_clicked = st.button(
                "Continue →",
                key="_auth_continue",
                use_container_width=True,
            )

        if continue_clicked:
            cleaned = email_input.strip().lower()
            if not cleaned:
                st.error("Please enter your email.")
            elif not _valid_email(cleaned):
                st.error("Please enter a valid email address.")
            else:
                st.session_state[_SESSION_KEY] = cleaned
                st.rerun()

        st.markdown(
            '<hr style="border-color:#1a1a1a;margin:12px 0;">',
            unsafe_allow_html=True,
        )
        return None


# ── Paywall ───────────────────────────────────────────────────────────────────

def render_paywall(email: str, analyses_used: int) -> bool:
    """Render the upgrade prompt.

    Returns True if the user just completed a payment verification.
    """
    # Check for Stripe session_id in URL (post-payment redirect)
    if check_session_upgrade(email):
        st.rerun()
        return True

    st.markdown(
        f"""
        <div style="background:#0d0d0d;border:1.5px solid #FF444430;
                    border-radius:16px;padding:36px 32px;margin:24px 0;
                    text-align:center;">
            <div style="font-size:36px;margin-bottom:16px;">⚽</div>
            <div style="color:#fff;font-size:22px;font-weight:900;
                        letter-spacing:-0.5px;margin-bottom:8px;">
                You've used your free analysis
            </div>
            <div style="color:#555;font-size:14px;line-height:1.6;margin-bottom:28px;
                        max-width:380px;margin-left:auto;margin-right:auto;">
                You've used {analyses_used} of 1 free analysis.
                Upgrade to Pro to unlock unlimited AI coaching sessions.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Pricing cards
    col_free, col_pro, col_club = st.columns(3, gap="medium")

    with col_free:
        st.markdown(
            """
            <div style="background:#111;border:1.5px solid #1e1e1e;
                        border-radius:14px;padding:24px;text-align:center;height:100%;">
                <div style="color:#555;font-size:10px;letter-spacing:3px;
                            text-transform:uppercase;font-weight:700;margin-bottom:10px;">
                    Current Plan
                </div>
                <div style="color:#fff;font-size:28px;font-weight:900;margin-bottom:4px;">
                    Free
                </div>
                <div style="color:#444;font-size:13px;margin-bottom:16px;">
                    1 analysis total
                </div>
                <div style="color:#333;font-size:12px;line-height:1.7;">
                    1 AI analysis<br>
                    Basic coaching report<br>
                    <span style="color:#FF4444;">No PDF export</span><br>
                    <span style="color:#FF4444;">No session history</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_pro:
        st.markdown(
            """
            <div style="background:linear-gradient(135deg,#00FF8710,#00FF8705);
                        border:1.5px solid #00FF8760;border-radius:14px;
                        padding:24px;text-align:center;height:100%;position:relative;">
                <div style="position:absolute;top:-12px;left:50%;transform:translateX(-50%);
                            background:#00FF87;color:#0a0a0a;font-size:10px;font-weight:800;
                            letter-spacing:2px;text-transform:uppercase;padding:4px 14px;
                            border-radius:100px;">Most Popular</div>
                <div style="color:#00FF87;font-size:10px;letter-spacing:3px;
                            text-transform:uppercase;font-weight:700;margin-bottom:10px;
                            margin-top:12px;">Pro</div>
                <div style="color:#fff;font-size:28px;font-weight:900;margin-bottom:4px;">
                    £9.99
                </div>
                <div style="color:#555;font-size:12px;margin-bottom:16px;">per month</div>
                <div style="color:#ccc;font-size:12px;line-height:1.7;">
                    Unlimited analyses<br>
                    Full AI coaching reports<br>
                    PDF + Stat Card export<br>
                    Session history<br>
                    7-day training plans
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button(
            "Upgrade to Pro →",
            key="_paywall_pro",
            use_container_width=True,
        ):
            checkout_url = create_checkout_session(
                email=email,
                plan="pro",
                success_url=_success_url(),
                cancel_url=_cancel_url(),
            )
            if checkout_url:
                st.markdown(
                    f'<meta http-equiv="refresh" content="0;url={checkout_url}">',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<a href="{checkout_url}" target="_self" style="color:#00FF87;">'
                    f"Click here if not redirected automatically</a>",
                    unsafe_allow_html=True,
                )
            else:
                st.error(
                    "Payment system is not configured yet. "
                    "Please contact support or try again later."
                )

    with col_club:
        st.markdown(
            """
            <div style="background:#111;border:1.5px solid #1e1e1e;
                        border-radius:14px;padding:24px;text-align:center;height:100%;">
                <div style="color:#FFC700;font-size:10px;letter-spacing:3px;
                            text-transform:uppercase;font-weight:700;margin-bottom:10px;">
                    Club
                </div>
                <div style="color:#fff;font-size:28px;font-weight:900;margin-bottom:4px;">
                    £49
                </div>
                <div style="color:#555;font-size:12px;margin-bottom:16px;">per month</div>
                <div style="color:#ccc;font-size:12px;line-height:1.7;">
                    Everything in Pro<br>
                    Up to 10 coaches<br>
                    Team Dashboard<br>
                    Squad analytics<br>
                    Priority support
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button(
            "Get Club Plan →",
            key="_paywall_club",
            use_container_width=True,
        ):
            checkout_url = create_checkout_session(
                email=email,
                plan="club",
                success_url=_success_url(),
                cancel_url=_cancel_url(),
            )
            if checkout_url:
                st.markdown(
                    f'<meta http-equiv="refresh" content="0;url={checkout_url}">',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<a href="{checkout_url}" target="_self" style="color:#FFC700;">'
                    f"Click here if not redirected automatically</a>",
                    unsafe_allow_html=True,
                )
            else:
                st.error(
                    "Payment system is not configured yet. "
                    "Please contact support or try again later."
                )

    return False


# ── Session upgrade check ─────────────────────────────────────────────────────

def check_session_upgrade(email: str) -> bool:
    """Check URL params for a Stripe session_id, verify the payment,
    and upgrade the user if valid.

    Returns True if user was just upgraded, False otherwise.
    """
    # Avoid re-checking on the same page load
    if st.session_state.get(_JUST_UPGRADED_KEY):
        return False

    try:
        session_id = st.query_params.get("session_id", "")
    except Exception:
        return False

    if not session_id:
        return False

    result = verify_checkout_session(session_id)
    if not result:
        return False

    # Mark as pro in database
    customer_id = result.get("customer_id") or ""
    subscription_id = result.get("subscription_id") or ""
    set_pro(email, customer_id, subscription_id)

    # Clear the session_id from URL params to avoid re-processing
    try:
        st.query_params.pop("session_id", None)
    except Exception:
        pass

    st.session_state[_JUST_UPGRADED_KEY] = True

    st.success(
        "Payment confirmed! Welcome to Pro. You now have unlimited analyses."
    )
    return True
