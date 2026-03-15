"""
Tactify — AI Soccer Coaching Platform
Nike/Adidas lab aesthetic: pure black, neon green, bold editorial typography.
"""

import base64
import html as _html
import io
import json as _json
import os
import urllib.parse
import zlib

import streamlit as st
import streamlit.components.v1 as st_components
from dotenv import load_dotenv

try:
    from knowledge_base import POSITIONS, PLAY_TYPES, AGE_GROUPS
    from analyzer import (analyze_media, generate_coaching_audio, compare_sessions,
                           generate_comparison_audio, analyze_team_patterns,
                           merge_audio_into_video, create_annotated_video_simple)
except Exception as _import_err:
    import traceback as _tb
    st.set_page_config(page_title="Tactify", page_icon="⚽")
    st.error(f"**Startup import error:** {_import_err}")
    st.code(_tb.format_exc(), language="text")
    st.stop()

load_dotenv()
print("CHECKPOINT 1: imports OK, dotenv loaded")

# ── Page config ───────────────────────────────────────────────────────────────

print("CHECKPOINT 2: calling set_page_config")
st.set_page_config(
    page_title="Tactify · AI Soccer Coaching",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)
print("CHECKPOINT 3: set_page_config OK")

# ── Global CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ─ Base ─ */
.stApp { background: #0a0a0a; }
.main .block-container { padding: 0 2.5rem 5rem; max-width: 1300px; }
#MainMenu, footer, header, .stDeployButton { visibility: hidden; }

/* ─ Upload zone ─ */
[data-testid="stFileUploader"] {
    background: #111 !important;
    border: 1.5px dashed #2a2a2a !important;
    border-radius: 12px !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: #00FF87 !important;
}

/* ─ Selectbox ─ */
.stSelectbox > div > div {
    background: #111 !important;
    border: 1.5px solid #1e1e1e !important;
    border-radius: 10px !important;
    color: #fff !important;
}

/* ─ Text area ─ */
.stTextArea textarea {
    background: #111 !important;
    border: 1.5px solid #1e1e1e !important;
    border-radius: 10px !important;
    color: #fff !important;
}

/* ─ Button ─ */
.stButton > button {
    background: #00FF87 !important;
    color: #0a0a0a !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 800 !important;
    font-size: 14px !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    padding: 0.7rem 1.5rem !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    background: #00e87a !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 8px 24px rgba(0,255,135,0.25) !important;
}
.stButton > button:disabled {
    background: #1a1a1a !important;
    color: #444 !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ─ Download button ─ */
[data-testid="stDownloadButton"] > button {
    background: transparent !important;
    color: #00FF87 !important;
    border: 1.5px solid #00FF87 !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    letter-spacing: 1px !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background: #00FF8715 !important;
}

/* ─ Spinner ─ */
.stSpinner > div { border-top-color: #00FF87 !important; }

/* ─ Caption ─ */
.stCaption { color: #444 !important; font-size: 12px !important; }

/* ─ Divider ─ */
hr { border-color: #1a1a1a !important; margin: 2rem 0 !important; }

/* ─ Tabs ─ */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #1a1a1a !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #444 !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    padding: 12px 24px !important;
}
.stTabs [aria-selected="true"] {
    color: #00FF87 !important;
    border-bottom: 2px solid #00FF87 !important;
}
</style>
""", unsafe_allow_html=True)


# ── Utilities ─────────────────────────────────────────────────────────────────

def e(t) -> str:
    return _html.escape(str(t))

def label(text: str) -> str:
    st.markdown(
        f'<div style="color:#444;font-size:10px;letter-spacing:3px;'
        f'text-transform:uppercase;font-weight:700;margin-bottom:10px;">{e(text)}</div>',
        unsafe_allow_html=True,
    )

def gap(px=20):
    st.markdown(f'<div style="height:{px}px"></div>', unsafe_allow_html=True)

def score_color(v) -> str:
    v = float(v)
    if v >= 8: return "#00FF87"
    if v >= 6: return "#FFC700"
    return "#FF4444"


# ── Section: Score Dashboard ──────────────────────────────────────────────────

def render_scores(scores: dict):
    vals  = [scores.get(k, 5) for k in ("technique","body_position","spatial_awareness","decision_making","effort")]
    overall = round(sum(vals) / len(vals), 1)
    oc    = score_color(overall)

    # Overall score hero
    st.markdown(f"""
    <div style="background:#111;border:1.5px solid #1e1e1e;border-radius:14px;
                padding:28px 24px 20px;margin-bottom:16px;text-align:center;">
        <div style="font-size:72px;font-weight:900;color:{oc};
                    line-height:1;letter-spacing:-3px;font-family:'Inter',sans-serif;">{overall}</div>
        <div style="color:#333;font-size:10px;letter-spacing:4px;
                    text-transform:uppercase;font-weight:700;margin-top:8px;">Overall Score</div>
    </div>
    """, unsafe_allow_html=True)

    # Category bars
    categories = [
        ("Technique",         "technique"),
        ("Body Position",     "body_position"),
        ("Spatial Awareness", "spatial_awareness"),
        ("Decision Making",   "decision_making"),
        ("Effort",            "effort"),
    ]
    st.markdown('<div style="background:#111;border:1.5px solid #1e1e1e;border-radius:14px;padding:20px 24px;">', unsafe_allow_html=True)
    for lbl, key in categories:
        v  = scores.get(key, 5)
        c  = score_color(v)
        pct = v * 10
        st.markdown(f"""
        <div style="margin-bottom:16px;">
            <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:7px;">
                <span style="color:#666;font-size:11px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;">{e(lbl)}</span>
                <span style="color:#fff;font-size:18px;font-weight:900;letter-spacing:-0.5px;">{v}<span style="color:#2a2a2a;font-size:12px;font-weight:400;">/10</span></span>
            </div>
            <div style="background:#1a1a1a;border-radius:3px;height:4px;overflow:hidden;">
                <div style="width:{pct}%;height:100%;background:{c};border-radius:3px;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ── Section: Annotation Legend ────────────────────────────────────────────────

def render_annotation_legend(annotations: list):
    sev_colors = {"strength": "#00FF87", "warning": "#FFC700", "error": "#FF4444"}
    sev_icons  = {"strength": "✓", "warning": "!", "error": "✗"}

    st.markdown('<div style="background:#111;border:1.5px solid #1e1e1e;border-radius:14px;padding:20px 24px;">', unsafe_allow_html=True)
    for ann in annotations[:6]:
        num   = ann.get("number", 1)
        lbl   = e(ann.get("label", ""))
        note  = e(ann.get("note", ""))
        sev   = ann.get("severity", "warning")
        c     = sev_colors.get(sev, "#FFC700")
        icon  = sev_icons.get(sev, "!")

        st.markdown(f"""
        <div style="display:flex;gap:16px;padding:13px 0;
                    border-bottom:1px solid #1a1a1a;align-items:flex-start;">
            <div style="width:32px;height:32px;border-radius:50%;
                        background:{c}18;border:1.5px solid {c};
                        display:flex;align-items:center;justify-content:center;
                        font-weight:900;font-size:13px;color:{c};flex-shrink:0;">{num}</div>
            <div style="flex:1;min-width:0;">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap;">
                    <span style="color:#fff;font-weight:700;font-size:13px;">{lbl}</span>
                    <span style="color:{c};font-size:10px;background:{c}15;
                                 padding:2px 8px;border-radius:100px;letter-spacing:1px;
                                 font-weight:700;text-transform:uppercase;">{icon} {sev}</span>
                </div>
                <div style="color:#555;font-size:13px;line-height:1.55;">{note}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ── Section: Insights ─────────────────────────────────────────────────────────

def render_insights(strengths: list, improvements: list):
    c_s, c_i = st.columns(2, gap="medium")

    with c_s:
        st.markdown('<div style="background:#111;border:1.5px solid #00FF8730;border-radius:14px;padding:22px;">', unsafe_allow_html=True)
        st.markdown('<div style="color:#00FF87;font-size:10px;letter-spacing:3px;text-transform:uppercase;font-weight:700;margin-bottom:14px;">Strengths</div>', unsafe_allow_html=True)
        for s in strengths:
            st.markdown(f'<div style="color:#bbb;font-size:13px;line-height:1.6;padding:9px 0;border-bottom:1px solid #1a1a1a;display:flex;gap:10px;"><span style="color:#00FF87;flex-shrink:0;margin-top:1px;">✓</span>{e(s)}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with c_i:
        st.markdown('<div style="background:#111;border:1.5px solid #FFC70030;border-radius:14px;padding:22px;">', unsafe_allow_html=True)
        st.markdown('<div style="color:#FFC700;font-size:10px;letter-spacing:3px;text-transform:uppercase;font-weight:700;margin-bottom:14px;">Improve</div>', unsafe_allow_html=True)
        for s in improvements:
            st.markdown(f'<div style="color:#bbb;font-size:13px;line-height:1.6;padding:9px 0;border-bottom:1px solid #1a1a1a;display:flex;gap:10px;"><span style="color:#FFC700;flex-shrink:0;margin-top:1px;">→</span>{e(s)}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ── Section: Drill Cards ──────────────────────────────────────────────────────

def render_drills(drills: list):
    icons = ["◎", "▷", "◈"]
    cols  = st.columns(min(len(drills), 3), gap="medium")
    for i, (col, drill) in enumerate(zip(cols, drills[:3])):
        with col:
            st.markdown(f"""
            <div style="background:#111;border:1.5px solid #1e1e1e;border-radius:14px;padding:24px;height:100%;">
                <div style="color:#00FF87;font-size:22px;margin-bottom:14px;">{icons[i]}</div>
                <div style="color:#fff;font-size:14px;font-weight:800;margin-bottom:8px;line-height:1.3;">{e(drill.get('name',''))}</div>
                <div style="display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap;">
                    <span style="color:#00FF87;background:#00FF8715;border-radius:100px;
                                 padding:2px 10px;font-size:11px;font-weight:700;letter-spacing:1px;">
                        {e(drill.get('duration',''))}
                    </span>
                    <span style="color:#444;background:#1a1a1a;border-radius:100px;
                                 padding:2px 10px;font-size:11px;letter-spacing:0.5px;">
                        {e(drill.get('focus',''))}
                    </span>
                </div>
                <div style="color:#555;font-size:13px;line-height:1.65;">{e(drill.get('description',''))}</div>
            </div>
            """, unsafe_allow_html=True)


# ── Section: Pro Reference ────────────────────────────────────────────────────

def render_pro_reference(ref: dict):
    player        = ref.get("player", "")
    team          = ref.get("team", "")
    note          = ref.get("note", "")
    youtube_query = ref.get("youtube_query", "")
    initials      = "".join(w[0] for w in player.split()[:2]).upper() if player else "??"

    col_card, col_vid = st.columns([1, 1.4], gap="large")

    with col_card:
        st.markdown(f"""
        <div style="background:#111;border:1.5px solid #1e1e1e;border-radius:14px;
                    padding:26px;height:100%;">
            <div style="display:flex;align-items:flex-start;gap:18px;margin-bottom:16px;">
                <div style="width:52px;height:52px;border-radius:50%;
                            background:linear-gradient(135deg,#00FF87,#00cc6a);
                            display:flex;align-items:center;justify-content:center;
                            font-size:18px;font-weight:900;color:#0a0a0a;flex-shrink:0;
                            font-family:'Inter',sans-serif;">{e(initials)}</div>
                <div>
                    <div style="color:#333;font-size:10px;letter-spacing:3px;
                                text-transform:uppercase;font-weight:700;margin-bottom:4px;">Study This Player</div>
                    <div style="color:#fff;font-weight:900;font-size:20px;
                                letter-spacing:-0.5px;">{e(player)}</div>
                    <div style="color:#00FF87;font-size:12px;font-weight:600;
                                letter-spacing:1px;">{e(team)}</div>
                </div>
            </div>
            <div style="color:#555;font-size:13px;line-height:1.65;
                        font-style:italic;margin-bottom:18px;">"{e(note)}"</div>
        </div>
        """, unsafe_allow_html=True)

        if youtube_query:
            yt_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(youtube_query)}"
            st.markdown(f"""
            <a href="{yt_url}" target="_blank" style="
                display:inline-flex;align-items:center;gap:8px;margin-top:10px;
                background:#FF0000;color:#fff;text-decoration:none;
                padding:10px 18px;border-radius:8px;font-size:12px;
                font-weight:700;letter-spacing:1px;text-transform:uppercase;">
                ▶ Watch on YouTube
            </a>
            """, unsafe_allow_html=True)

    with col_vid:
        if youtube_query:
            yt_search = f"https://www.youtube.com/results?search_query={urllib.parse.quote(youtube_query)}"
            st.markdown(f"""
            <a href="{yt_search}" target="_blank" style="text-decoration:none;">
                <div style="background:#111;border:1.5px solid #1e1e1e;border-radius:14px;
                            height:220px;display:flex;flex-direction:column;
                            align-items:center;justify-content:center;gap:16px;
                            cursor:pointer;transition:border-color 0.2s;"
                     onmouseover="this.style.borderColor='#FF0000'"
                     onmouseout="this.style.borderColor='#1e1e1e'">
                    <div style="width:64px;height:44px;background:#FF0000;border-radius:10px;
                                display:flex;align-items:center;justify-content:center;">
                        <div style="width:0;height:0;border-top:11px solid transparent;
                                    border-bottom:11px solid transparent;
                                    border-left:18px solid #fff;margin-left:4px;"></div>
                    </div>
                    <div style="text-align:center;padding:0 20px;">
                        <div style="color:#fff;font-size:13px;font-weight:700;margin-bottom:6px;">
                            Watch Reference Clip
                        </div>
                        <div style="color:#444;font-size:11px;line-height:1.5;">
                            {e(youtube_query)}
                        </div>
                    </div>
                    <div style="color:#FF0000;font-size:10px;letter-spacing:2px;
                                text-transform:uppercase;font-weight:700;">
                        Opens on YouTube →
                    </div>
                </div>
            </a>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:#111;border:1.5px dashed #1e1e1e;border-radius:14px;
                        height:220px;display:flex;align-items:center;justify-content:center;">
                <div style="color:#333;font-size:13px;">No reference clip available</div>
            </div>
            """, unsafe_allow_html=True)


# ── Section: Priority Fix ─────────────────────────────────────────────────────

def render_priority_fix(pf: dict):
    drill = pf.get("drill", {})
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#00FF8710,#00FF8705);
                border:1.5px solid #00FF8740;border-radius:16px;padding:28px 32px;">
        <div style="color:#00FF87;font-size:10px;letter-spacing:3px;
                    text-transform:uppercase;font-weight:700;margin-bottom:6px;">
            ★ Priority Focus This Session
        </div>
        <div style="color:#fff;font-size:22px;font-weight:900;
                    letter-spacing:-0.5px;margin-bottom:20px;line-height:1.2;">
            {e(pf.get("title",""))}
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px;">
            <div>
                <div style="color:#666;font-size:10px;letter-spacing:2px;
                            text-transform:uppercase;font-weight:700;margin-bottom:6px;">What's wrong</div>
                <div style="color:#ccc;font-size:14px;line-height:1.6;">{e(pf.get("what",""))}</div>
            </div>
            <div>
                <div style="color:#666;font-size:10px;letter-spacing:2px;
                            text-transform:uppercase;font-weight:700;margin-bottom:6px;">Why it costs you</div>
                <div style="color:#ccc;font-size:14px;line-height:1.6;">{e(pf.get("why",""))}</div>
            </div>
        </div>
        <div style="background:#00FF8718;border:1px solid #00FF8760;border-radius:10px;
                    padding:14px 20px;margin-bottom:24px;display:flex;align-items:center;gap:14px;">
            <div style="color:#00FF87;font-size:22px;">💬</div>
            <div>
                <div style="color:#00FF87;font-size:10px;letter-spacing:2px;
                            text-transform:uppercase;font-weight:700;margin-bottom:3px;">Your Cue</div>
                <div style="color:#fff;font-size:16px;font-weight:700;font-style:italic;">
                    "{e(pf.get("cue",""))}"
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if drill:
        gap(12)
        st.markdown(f"""
        <div style="background:#111;border:1.5px solid #1e1e1e;border-radius:14px;padding:22px 28px;">
            <div style="color:#666;font-size:10px;letter-spacing:2px;
                        text-transform:uppercase;font-weight:700;margin-bottom:14px;">Drill to Fix It</div>
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap;">
                <div style="color:#fff;font-size:16px;font-weight:800;">{e(drill.get("name",""))}</div>
                <span style="color:#00FF87;background:#00FF8715;border-radius:100px;
                             padding:2px 10px;font-size:11px;font-weight:700;">⏱ {e(drill.get("duration",""))}</span>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;">
                <div>
                    <div style="color:#444;font-size:10px;letter-spacing:2px;
                                text-transform:uppercase;font-weight:700;margin-bottom:6px;">Setup</div>
                    <div style="color:#999;font-size:13px;line-height:1.6;">{e(drill.get("setup",""))}</div>
                </div>
                <div>
                    <div style="color:#444;font-size:10px;letter-spacing:2px;
                                text-transform:uppercase;font-weight:700;margin-bottom:6px;">Focus on</div>
                    <div style="color:#999;font-size:13px;line-height:1.6;">{e(drill.get("focus",""))}</div>
                </div>
                <div>
                    <div style="color:#00FF87;font-size:10px;letter-spacing:2px;
                                text-transform:uppercase;font-weight:700;margin-bottom:6px;">You know it's working when</div>
                    <div style="color:#999;font-size:13px;line-height:1.6;">{e(drill.get("know_its_working",""))}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ── Section: Key Moments ──────────────────────────────────────────────────────

def render_key_moments(key_frames: list, best: dict, worst: dict):
    col_w, col_b = st.columns(2, gap="medium")

    with col_w:
        st.markdown("""
        <div style="color:#FF4444;font-size:10px;letter-spacing:3px;
                    text-transform:uppercase;font-weight:700;margin-bottom:10px;">
            ✗ Moment to Fix
        </div>""", unsafe_allow_html=True)
        frame_idx = max(0, worst.get("frame", 1) - 1)
        img = key_frames[frame_idx] if frame_idx < len(key_frames) else (key_frames[0] if key_frames else None)
        if img:
            st.image(img, use_container_width=True)
        for lbl, key, color in [
            ("What", "what", "#ccc"),
            ("Why it happens", "cause", "#888"),
            ("Game consequence", "effect", "#FF4444"),
        ]:
            val = worst.get(key, "")
            if val:
                st.markdown(f"""
                <div style="padding:8px 0;border-bottom:1px solid #1a1a1a;">
                    <div style="color:#444;font-size:10px;letter-spacing:2px;
                                text-transform:uppercase;font-weight:700;margin-bottom:3px;">{lbl}</div>
                    <div style="color:{color};font-size:13px;line-height:1.5;">{e(val)}</div>
                </div>""", unsafe_allow_html=True)

    with col_b:
        st.markdown("""
        <div style="color:#00FF87;font-size:10px;letter-spacing:3px;
                    text-transform:uppercase;font-weight:700;margin-bottom:10px;">
            ✓ Best Moment
        </div>""", unsafe_allow_html=True)
        frame_idx = max(0, best.get("frame", 1) - 1)
        img = key_frames[frame_idx] if frame_idx < len(key_frames) else (key_frames[0] if key_frames else None)
        if img:
            st.image(img, use_container_width=True)
        desc = best.get("description", "")
        if desc:
            st.markdown(f"""
            <div style="padding:8px 0;">
                <div style="color:#444;font-size:10px;letter-spacing:2px;
                            text-transform:uppercase;font-weight:700;margin-bottom:3px;">What you did well</div>
                <div style="color:#00FF87;font-size:13px;line-height:1.5;">{e(desc)}</div>
            </div>""", unsafe_allow_html=True)


# ── Section: Fix Cards ────────────────────────────────────────────────────────

def render_fix_cards(fix_cards: list):
    cols = st.columns(min(len(fix_cards), 3), gap="medium")
    sev_colors = {"error": "#FF4444", "warning": "#FFC700", "strength": "#00FF87"}

    for i, (col, card) in enumerate(zip(cols, fix_cards[:3])):
        with col:
            drill = card.get("drill", {})
            st.markdown(f"""
            <div style="background:#111;border:1.5px solid #1e1e1e;
                        border-radius:14px;padding:22px;height:100%;">
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;">
                    <div style="width:28px;height:28px;border-radius:50%;
                                background:#FF444420;border:1.5px solid #FF4444;
                                display:flex;align-items:center;justify-content:center;
                                font-weight:900;font-size:12px;color:#FF4444;flex-shrink:0;">{i+1}</div>
                    <div style="color:#fff;font-weight:800;font-size:14px;">{e(card.get("mistake",""))}</div>
                </div>
                <div style="margin-bottom:12px;">
                    <div style="color:#FF4444;font-size:10px;letter-spacing:2px;
                                text-transform:uppercase;font-weight:700;margin-bottom:4px;">Why it costs you</div>
                    <div style="color:#888;font-size:13px;line-height:1.5;">{e(card.get("why_it_matters",""))}</div>
                </div>
                <div style="margin-bottom:12px;">
                    <div style="color:#FFC700;font-size:10px;letter-spacing:2px;
                                text-transform:uppercase;font-weight:700;margin-bottom:4px;">Fix it</div>
                    <div style="color:#bbb;font-size:13px;line-height:1.5;">{e(card.get("correction",""))}</div>
                </div>
                <div style="background:#00FF8712;border:1px solid #00FF8730;border-radius:8px;
                            padding:10px 14px;margin-bottom:14px;">
                    <div style="color:#00FF87;font-size:11px;font-style:italic;font-weight:600;">
                        "{e(card.get("cue",""))}"
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if drill:
                gap(6)
                st.markdown(f"""
                <div style="background:#0d0d0d;border:1px solid #1a1a1a;border-radius:10px;padding:14px 16px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <div style="color:#888;font-size:12px;font-weight:700;">{e(drill.get("name",""))}</div>
                        <span style="color:#00FF87;background:#00FF8715;border-radius:100px;
                                     padding:1px 8px;font-size:11px;">⏱ {e(drill.get("duration",""))}</span>
                    </div>
                    <div style="color:#555;font-size:12px;line-height:1.5;margin-bottom:8px;">
                        {e(drill.get("setup",""))}
                    </div>
                    <div style="color:#00FF87;font-size:11px;font-style:italic;">
                        ✓ {e(drill.get("know_its_working",""))}
                    </div>
                </div>
                """, unsafe_allow_html=True)


# ── Section: Report Card (download) ──────────────────────────────────────────

def build_report_card_html(data: dict, key_frames: list, position: str, age_group: str) -> str:
    import base64

    scores  = data.get("scores", {})
    vals    = [scores.get(k, 5) for k in ("technique","body_position","spatial_awareness","decision_making","effort")]
    overall = round(sum(vals) / max(len(vals), 1), 1)

    pf     = data.get("priority_fix", {})
    worst  = data.get("worst_moment", {})
    ref    = data.get("pro_reference", {})

    # Embed worst-moment frame as base64
    img_html = ""
    frame_idx = max(0, worst.get("frame", 1) - 1)
    if key_frames and frame_idx < len(key_frames):
        img_b64 = base64.b64encode(key_frames[frame_idx]).decode()
        img_html = f'<img src="data:image/jpeg;base64,{img_b64}" style="width:100%;border-radius:8px;margin:16px 0;" />'

    oc = "#00FF87" if overall >= 8 else "#FFC700" if overall >= 6 else "#FF4444"

    score_rows = ""
    for lbl, key in [("Technique","technique"),("Body Position","body_position"),
                     ("Spatial Awareness","spatial_awareness"),("Decision Making","decision_making"),("Effort","effort")]:
        v   = scores.get(key, 5)
        c   = "#00FF87" if v >= 8 else "#FFC700" if v >= 6 else "#FF4444"
        pct = v * 10
        score_rows += f"""
        <div style="margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                <span style="color:#666;font-size:12px;">{lbl}</span>
                <span style="color:#fff;font-weight:700;font-size:12px;">{v}/10</span>
            </div>
            <div style="background:#1a1a1a;border-radius:3px;height:5px;">
                <div style="width:{pct}%;height:100%;background:{c};border-radius:3px;"></div>
            </div>
        </div>"""

    drill = pf.get("drill", {})
    drill_html = ""
    if drill:
        drill_html = f"""
        <div style="margin-top:16px;background:#0d0d0d;border:1px solid #1e1e1e;border-radius:8px;padding:14px;">
            <div style="color:#00FF87;font-size:11px;letter-spacing:2px;text-transform:uppercase;font-weight:700;margin-bottom:6px;">
                Drill — {e(drill.get("name",""))} · {e(drill.get("duration",""))}
            </div>
            <div style="color:#999;font-size:12px;line-height:1.6;margin-bottom:8px;">{e(drill.get("setup",""))}</div>
            <div style="color:#00FF87;font-size:12px;font-style:italic;">✓ {e(drill.get("know_its_working",""))}</div>
        </div>"""

    from datetime import date
    today = date.today().strftime("%B %d, %Y")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<title>Tactify — Player Report</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:#0a0a0a; color:#fff; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; padding:32px; max-width:800px; margin:0 auto; }}
  @media print {{
    body {{ background:#fff; color:#111; }}
    .dark-bg {{ background:#f5f5f5 !important; border-color:#ddd !important; }}
  }}
</style>
</head>
<body>
  <div style="display:flex;justify-content:space-between;align-items:flex-end;
              border-bottom:1px solid #1e1e1e;padding-bottom:20px;margin-bottom:24px;">
    <div>
      <div style="font-size:24px;font-weight:900;letter-spacing:-0.5px;">⚽ TACTIFY</div>
      <div style="color:#444;font-size:11px;letter-spacing:3px;text-transform:uppercase;margin-top:4px;">
        Player Analysis Report
      </div>
    </div>
    <div style="text-align:right;">
      <div style="color:#666;font-size:12px;">{today}</div>
      <div style="color:#666;font-size:12px;">{e(position)} · {e(age_group)}</div>
    </div>
  </div>

  <div style="display:grid;grid-template-columns:140px 1fr;gap:24px;margin-bottom:28px;">
    <div style="background:#111;border:1px solid #1e1e1e;border-radius:12px;padding:20px;text-align:center;">
      <div style="font-size:52px;font-weight:900;color:{oc};line-height:1;">{overall}</div>
      <div style="color:#444;font-size:10px;letter-spacing:3px;text-transform:uppercase;margin-top:6px;">Score</div>
    </div>
    <div style="background:#111;border:1px solid #1e1e1e;border-radius:12px;padding:20px;">
      {score_rows}
    </div>
  </div>

  {img_html}

  <div style="background:#00FF8710;border:1.5px solid #00FF8740;border-radius:12px;
              padding:20px;margin-bottom:20px;">
    <div style="color:#00FF87;font-size:10px;letter-spacing:3px;
                text-transform:uppercase;font-weight:700;margin-bottom:8px;">★ Priority Focus</div>
    <div style="font-size:18px;font-weight:900;margin-bottom:10px;">{e(pf.get("title",""))}</div>
    <div style="color:#aaa;font-size:13px;line-height:1.6;margin-bottom:10px;">{e(pf.get("what",""))}</div>
    <div style="background:#00FF8720;border-radius:8px;padding:10px 14px;
                color:#00FF87;font-style:italic;font-weight:700;font-size:14px;">
      "{e(pf.get("cue",""))}"
    </div>
    {drill_html}
  </div>

  <div style="background:#111;border:1px solid #1e1e1e;border-radius:12px;padding:20px;">
    <div style="color:#666;font-size:10px;letter-spacing:3px;text-transform:uppercase;
                font-weight:700;margin-bottom:8px;">Professional Reference</div>
    <div style="font-weight:800;font-size:16px;">{e(ref.get("player",""))}</div>
    <div style="color:#00FF87;font-size:12px;margin-bottom:8px;">{e(ref.get("team",""))}</div>
    <div style="color:#666;font-size:13px;font-style:italic;">{e(ref.get("note",""))}</div>
  </div>

  <div style="margin-top:24px;color:#333;font-size:11px;text-align:center;letter-spacing:1px;">
    Generated by Tactify · AI Soccer Coaching Platform
  </div>
</body>
</html>"""


# ── Share link helpers ────────────────────────────────────────────────────────

_SHAREABLE_KEYS = ("summary", "scores", "priority_fix", "fix_cards",
                   "strengths", "best_moment", "worst_moment", "pro_reference")

def _encode_report(data: dict, position: str, age_group: str) -> str:
    payload = {k: data[k] for k in _SHAREABLE_KEYS if k in data}
    payload["_meta"] = {"position": position, "age_group": age_group}
    raw = _json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(zlib.compress(raw, level=9)).decode()

def _decode_report(encoded: str) -> dict | None:
    try:
        raw = zlib.decompress(base64.urlsafe_b64decode(encoded))
        return _json.loads(raw)
    except Exception:
        return None


# ── Shared report view (read-only, opened via URL) ────────────────────────────

def render_shared_report(data: dict):
    meta      = data.get("_meta", {})
    position  = meta.get("position", "Player")
    age_group = meta.get("age_group", "")
    scores    = data.get("scores", {})
    summary   = e(data.get("summary", ""))

    # Header badge
    st.markdown(f"""
    <div style="padding:32px 0 24px;border-bottom:1px solid #1a1a1a;margin-bottom:28px;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
            <span style="font-size:24px;">⚽</span>
            <span style="font-size:24px;font-weight:900;color:#fff;letter-spacing:-0.5px;">TACTIFY</span>
            <span style="background:#00FF8720;color:#00FF87;font-size:10px;font-weight:700;
                         letter-spacing:2px;text-transform:uppercase;padding:4px 12px;
                         border-radius:100px;border:1px solid #00FF8740;">Player Report</span>
        </div>
        <div style="color:#333;font-size:12px;">{e(position)} · {e(age_group)}</div>
    </div>
    """, unsafe_allow_html=True)

    # Summary
    st.markdown(f"""
    <div style="border-left:3px solid #00FF87;padding:16px 24px;
                background:#00FF870a;border-radius:0 10px 10px 0;margin-bottom:28px;">
        <div style="color:#00FF87;font-size:10px;letter-spacing:3px;
                    text-transform:uppercase;font-weight:700;margin-bottom:6px;">AI Assessment</div>
        <div style="color:#ddd;font-size:15px;line-height:1.6;font-style:italic;">"{summary}"</div>
    </div>
    """, unsafe_allow_html=True)

    # Scores
    if scores:
        label("Performance Scores")
        render_scores(scores)
        gap(28)

    # Priority fix
    if data.get("priority_fix"):
        label("Priority Focus This Session")
        render_priority_fix(data["priority_fix"])
        gap(28)

    # Fix cards
    if data.get("fix_cards"):
        label("Fix Cards · Mistakes & Drills")
        render_fix_cards(data["fix_cards"])
        gap(28)

    # Strengths
    if data.get("strengths"):
        label("What You're Doing Well")
        st.markdown('<div style="background:#111;border:1.5px solid #00FF8730;border-radius:14px;padding:22px;">', unsafe_allow_html=True)
        for s in data["strengths"]:
            st.markdown(f'<div style="color:#bbb;font-size:13px;line-height:1.6;padding:9px 0;border-bottom:1px solid #1a1a1a;display:flex;gap:10px;"><span style="color:#00FF87;flex-shrink:0;margin-top:1px;">✓</span>{e(s)}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        gap(28)

    # Pro reference
    if data.get("pro_reference"):
        label("Professional Reference")
        render_pro_reference(data["pro_reference"])


# ─────────────────────────────────────────────────────────────────────────────
# APP
# ─────────────────────────────────────────────────────────────────────────────

# ── Global exception hook — shows real traceback instead of "Oh no" ──────────
import sys as _sys
import traceback as _tb
_orig_excepthook = _sys.excepthook
def _st_excepthook(exc_type, exc_value, exc_tb):
    try:
        st.error(f"**App error:** {exc_type.__name__}: {exc_value}")
        st.code("".join(_tb.format_tb(exc_tb)), language="text")
    except Exception:
        pass
    _orig_excepthook(exc_type, exc_value, exc_tb)
_sys.excepthook = _st_excepthook

print("CHECKPOINT 4: reaching main app body")
# ── Shared report intercept ───────────────────────────────────────────────────
_report_param = st.query_params.get("report")
if _report_param:
    _shared = _decode_report(_report_param)
    if _shared:
        render_shared_report(_shared)
    else:
        st.error("This report link is invalid or has expired.")
    st.stop()

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("""
<div style="padding:40px 0 32px;border-bottom:1px solid #1a1a1a;margin-bottom:36px;">
    <div style="display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:12px;">
        <div style="display:flex;align-items:center;gap:16px;">
            <span style="font-size:32px;">⚽</span>
            <div>
                <div style="font-size:32px;font-weight:900;color:#fff;letter-spacing:-1px;
                            font-family:'Inter',sans-serif;line-height:1;">TACTIFY</div>
                <div style="font-size:10px;color:#333;letter-spacing:4px;
                            text-transform:uppercase;font-weight:600;margin-top:4px;">
                    AI Soccer Coaching Platform
                </div>
            </div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
            <div style="width:8px;height:8px;border-radius:50%;background:#00FF87;
                        box-shadow:0 0 8px #00FF87;"></div>
            <span style="color:#00FF87;font-size:11px;letter-spacing:2px;font-weight:700;text-transform:uppercase;">System Online</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

print("CHECKPOINT 5: creating tabs")
# ── Mode Tabs ─────────────────────────────────────────────────────────────────

tab_single, tab_compare, tab_team = st.tabs(["Single Session", "Before / After Comparison", "Team Dashboard"])
print("CHECKPOINT 6: tabs created")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Single Session
# ══════════════════════════════════════════════════════════════════════════════

print("CHECKPOINT 7: entering tab_single")
with tab_single:
    col_up, col_ctx = st.columns([1.5, 1], gap="large")

    with col_up:
        label("Upload Footage")
        uploaded_file = st.file_uploader(
            "footage",
            type=["jpg", "jpeg", "png", "mp4", "mov"],
            label_visibility="collapsed",
        )
        if uploaded_file:
            file_bytes = uploaded_file.read()
            is_video = uploaded_file.type in ("video/mp4", "video/quicktime")
            if is_video:
                st.video(io.BytesIO(file_bytes))
            else:
                st.image(file_bytes, use_container_width=True)

    with col_ctx:
        label("Analysis Context")
        position  = st.selectbox("Position",  POSITIONS,  index=6,  label_visibility="collapsed")
        play_type = st.selectbox("Play Type", PLAY_TYPES, index=8,  label_visibility="collapsed")
        age_group = st.selectbox("Age Group", AGE_GROUPS, index=3,  label_visibility="collapsed")
        notes     = st.text_area("Notes", height=80, label_visibility="collapsed",
                                  placeholder="e.g. right-footed striker, focus on off-ball movement…")
        gap(10)
        run = st.button("Run Analysis ▶", use_container_width=True, disabled=not uploaded_file)

    st.markdown('<hr>', unsafe_allow_html=True)

    # ── Results (single session) ───────────────────────────────────────────────

    if uploaded_file and run:
        is_video = uploaded_file.type in ("video/mp4", "video/quicktime")

        # ── Step 1: Claude analysis ────────────────────────────────────────────
        with st.spinner("Analyzing footage with AI…"):
            result = analyze_media(
                file_bytes=file_bytes,
                file_type=uploaded_file.type,
                position=position,
                play_type=play_type,
                age_group=age_group,
                additional_notes=notes,
            )

        if not result["success"]:
            st.error(f"Analysis failed: {result['error']}")
            st.stop()

        data        = result["data"]
        annotations = data.get("annotations", [])
        scores      = data.get("scores", {})
        summary     = e(data.get("summary", ""))

        # ── Step 2: Coaching audio ────────────────────────────────────────────
        try:
            with st.spinner("Generating coaching audio narration…"):
                audio_bytes = generate_coaching_audio(data, position)
        except Exception as _ae:
            audio_bytes = None

        # ── Step 3: Annotate video + merge audio (one-click experience) ───────
        final_video = None
        if is_video:
            try:
                with st.spinner("Adding coaching overlay to video…"):
                    annotated = create_annotated_video_simple(
                        file_bytes, annotations, scores
                    )
                base_video = annotated if annotated else file_bytes
                if audio_bytes:
                    with st.spinner("Merging coaching audio into video…"):
                        merged = merge_audio_into_video(base_video, audio_bytes)
                    final_video = merged if merged else base_video
                else:
                    final_video = base_video
            except Exception as _ve:
                final_video = file_bytes

        # ── Summary banner ─────────────────────────────────────────────────────
        st.markdown(f"""
        <div style="border-left:3px solid #00FF87;padding:16px 24px;
                    background:#00FF870a;border-radius:0 10px 10px 0;margin-bottom:16px;">
            <div style="color:#00FF87;font-size:10px;letter-spacing:3px;
                        text-transform:uppercase;font-weight:700;margin-bottom:6px;">AI Assessment</div>
            <div style="color:#ddd;font-size:15px;line-height:1.6;font-style:italic;">"{summary}"</div>
        </div>
        """, unsafe_allow_html=True)

        # ── Media + Scores ─────────────────────────────────────────────────────
        col_media, col_scores = st.columns([1.2, 1], gap="large")

        with col_media:
            if is_video:
                label("Coaching Video — Press Play")
                st.markdown(
                    '<div style="color:#555;font-size:11px;letter-spacing:1px;margin-bottom:8px;">'
                    'Audio coaching narration is embedded · dots and lines show focus areas</div>',
                    unsafe_allow_html=True,
                )
                st.video(final_video)

                # Annotated key frames with coaching legend
                if result.get("key_frames"):
                    gap(24)
                    label("Frame-by-Frame Breakdown")
                    kf_cols = st.columns(min(len(result["key_frames"]), 4), gap="small")
                    for i, (kf_col, kf) in enumerate(zip(kf_cols, result["key_frames"][:4])):
                        with kf_col:
                            st.image(kf, use_container_width=True)
                            st.markdown(f'<div style="color:#555;font-size:10px;text-align:center;margin-top:4px;letter-spacing:1px;">FRAME {i+1}</div>', unsafe_allow_html=True)
                    # Annotation legend
                    if annotations:
                        gap(12)
                        ann_html = '<div style="background:#0d0d0d;border:1px solid #1a1a1a;border-radius:10px;padding:16px 20px;">'
                        for ann in annotations[:6]:
                            sev  = ann.get("severity", "warning")
                            col  = {"strength": "#10B981", "warning": "#F59E0B", "error": "#EF4444"}.get(sev, "#F59E0B")
                            num  = ann.get("number", "")
                            lbl  = e(ann.get("label", ""))
                            note = e(ann.get("note", ""))
                            ann_html += (
                                f'<div style="display:flex;gap:12px;padding:8px 0;'
                                f'border-bottom:1px solid #141414;align-items:flex-start;">'
                                f'<div style="background:{col};color:#000;font-size:11px;font-weight:800;'
                                f'min-width:22px;height:22px;border-radius:50%;display:flex;'
                                f'align-items:center;justify-content:center;flex-shrink:0;">{num}</div>'
                                f'<div><div style="color:{col};font-size:11px;font-weight:700;'
                                f'text-transform:uppercase;letter-spacing:1px;">{lbl}</div>'
                                f'<div style="color:#777;font-size:12px;line-height:1.5;margin-top:2px;">{note}</div>'
                                f'</div></div>'
                            )
                        ann_html += '</div>'
                        st.markdown(ann_html, unsafe_allow_html=True)
            else:
                label("Annotated Analysis")
                display = result.get("annotated_image") or file_bytes
                st.image(display, use_container_width=True)
                # Still image annotation legend
                if annotations:
                    gap(12)
                    ann_html = '<div style="background:#0d0d0d;border:1px solid #1a1a1a;border-radius:10px;padding:16px 20px;">'
                    for ann in annotations[:6]:
                        sev  = ann.get("severity", "warning")
                        col  = {"strength": "#10B981", "warning": "#F59E0B", "error": "#EF4444"}.get(sev, "#F59E0B")
                        num  = ann.get("number", "")
                        lbl  = e(ann.get("label", ""))
                        note = e(ann.get("note", ""))
                        ann_html += (
                            f'<div style="display:flex;gap:12px;padding:8px 0;'
                            f'border-bottom:1px solid #141414;align-items:flex-start;">'
                            f'<div style="background:{col};color:#000;font-size:11px;font-weight:800;'
                            f'min-width:22px;height:22px;border-radius:50%;display:flex;'
                            f'align-items:center;justify-content:center;flex-shrink:0;">{num}</div>'
                            f'<div><div style="color:{col};font-size:11px;font-weight:700;'
                            f'text-transform:uppercase;letter-spacing:1px;">{lbl}</div>'
                            f'<div style="color:#777;font-size:12px;line-height:1.5;margin-top:2px;">{note}</div>'
                            f'</div></div>'
                        )
                    ann_html += '</div>'
                    st.markdown(ann_html, unsafe_allow_html=True)

        with col_scores:
            label("Performance Scores")
            if scores:
                render_scores(scores)

        # ── Priority Fix ───────────────────────────────────────────────────────
        if data.get("priority_fix"):
            gap(32)
            label("Priority Focus This Session")
            render_priority_fix(data["priority_fix"])

        # ── Key Moments ────────────────────────────────────────────────────────
        if result.get("key_frames") and (data.get("best_moment") or data.get("worst_moment")):
            gap(32)
            label("Key Moments")
            render_key_moments(
                result["key_frames"],
                data.get("best_moment", {}),
                data.get("worst_moment", {}),
            )

        # ── Fix Cards ──────────────────────────────────────────────────────────
        if data.get("fix_cards"):
            gap(32)
            label("Fix Cards · Mistakes & Drills")
            render_fix_cards(data["fix_cards"])

        # ── Strengths ──────────────────────────────────────────────────────────
        if data.get("strengths"):
            gap(32)
            label("What You're Doing Well")
            st.markdown('<div style="background:#111;border:1.5px solid #00FF8730;border-radius:14px;padding:22px;">', unsafe_allow_html=True)
            for s in data["strengths"]:
                st.markdown(f'<div style="color:#bbb;font-size:13px;line-height:1.6;padding:9px 0;border-bottom:1px solid #1a1a1a;display:flex;gap:10px;"><span style="color:#00FF87;flex-shrink:0;margin-top:1px;">✓</span>{e(s)}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # ── Pro reference ──────────────────────────────────────────────────────
        if data.get("pro_reference"):
            gap(32)
            label("Professional Reference")
            render_pro_reference(data["pro_reference"])

        # ── Share link ─────────────────────────────────────────────────────────
        gap(32)
        label("Share This Report")
        encoded     = _encode_report(data, position, age_group)
        base_url    = st.query_params.get("_base_url", "http://localhost:8501")
        share_url   = f"{base_url}/?report={encoded}"
        st.markdown(f"""
        <div style="background:#111;border:1.5px solid #00FF8730;border-radius:14px;padding:22px 26px;">
            <div style="color:#00FF87;font-size:10px;letter-spacing:3px;text-transform:uppercase;
                        font-weight:700;margin-bottom:10px;">🔗 Player Report Link</div>
            <div style="color:#555;font-size:12px;margin-bottom:14px;line-height:1.5;">
                Send this link directly to the player. They'll see their full report — scores,
                priority fix, fix cards, and pro reference — on any device, no login needed.
            </div>
            <div style="background:#0d0d0d;border:1px solid #1e1e1e;border-radius:8px;
                        padding:12px 16px;font-family:monospace;font-size:11px;color:#888;
                        word-break:break-all;line-height:1.6;">{share_url}</div>
        </div>
        """, unsafe_allow_html=True)
        gap(8)
        st_components.html(f"""
        <button onclick="navigator.clipboard.writeText('{share_url}').then(()=>{{
            this.textContent='✓ Copied!';
            this.style.background='#00FF87';
            this.style.color='#0a0a0a';
            setTimeout(()=>{{this.textContent='📋 Copy Link';this.style.background='transparent';this.style.color='#00FF87';}},2000);
        }})" style="
            background:transparent;color:#00FF87;border:1.5px solid #00FF87;
            border-radius:8px;padding:10px 20px;font-size:12px;font-weight:700;
            letter-spacing:1px;text-transform:uppercase;cursor:pointer;
            font-family:-apple-system,BlinkMacSystemFont,sans-serif;">
            📋 Copy Link
        </button>
        """, height=52)

        # ── Downloads ──────────────────────────────────────────────────────────
        gap(24)
        dl_cols = st.columns([1, 1, 1, 2])
        with dl_cols[0]:
            report_html = build_report_card_html(data, result.get("key_frames", []), position, age_group)
            st.download_button(
                "⬇ Player Report Card",
                data=report_html,
                file_name=f"tactify_report_{uploaded_file.name.rsplit('.', 1)[0]}.html",
                mime="text/html",
            )
        with dl_cols[1]:
            st.download_button(
                "⬇ Raw Data (JSON)",
                data=_json.dumps(data, indent=2),
                file_name=f"tactify_{uploaded_file.name.rsplit('.', 1)[0]}.json",
                mime="application/json",
            )
        if is_video and final_video:
            with dl_cols[2]:
                st.download_button(
                    "⬇ Coaching Video",
                    data=final_video,
                    file_name=f"tactify_coached_{uploaded_file.name}",
                    mime="video/mp4",
                )

    elif not uploaded_file:
        st.markdown("""
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                    height:280px;background:#111;border:1.5px dashed #1e1e1e;border-radius:14px;
                    text-align:center;padding:40px;">
            <div style="font-size:36px;margin-bottom:16px;opacity:0.25;">◎</div>
            <div style="color:#333;font-size:14px;font-weight:600;letter-spacing:0.5px;">
                Upload footage to begin analysis
            </div>
            <div style="color:#2a2a2a;font-size:12px;margin-top:8px;letter-spacing:1px;text-transform:uppercase;">
                Images · MP4 · MOV · Up to 5 minutes
            </div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Before / After Comparison
# ══════════════════════════════════════════════════════════════════════════════

with tab_compare:
    st.markdown("""
    <div style="color:#555;font-size:13px;line-height:1.7;margin-bottom:24px;">
        Upload two clips from different sessions. Tactify will analyse both and show you
        exactly what has improved, what still needs work, and what to focus on next.
    </div>
    """, unsafe_allow_html=True)

    # Context selectors (shared for both clips)
    ctx_cols = st.columns(3, gap="medium")
    with ctx_cols[0]:
        label("Position")
        cmp_position  = st.selectbox("cmp_pos",  POSITIONS,  index=6,  label_visibility="collapsed", key="cmp_pos")
    with ctx_cols[1]:
        label("Play Type")
        cmp_play_type = st.selectbox("cmp_play", PLAY_TYPES, index=8,  label_visibility="collapsed", key="cmp_play")
    with ctx_cols[2]:
        label("Age Group")
        cmp_age_group = st.selectbox("cmp_age",  AGE_GROUPS, index=3,  label_visibility="collapsed", key="cmp_age")

    gap(16)

    up_b, up_a = st.columns(2, gap="large")

    with up_b:
        st.markdown('<div style="color:#555;font-size:10px;letter-spacing:3px;text-transform:uppercase;font-weight:700;margin-bottom:8px;">Before</div>', unsafe_allow_html=True)
        before_file = st.file_uploader("before", type=["jpg","jpeg","png","mp4","mov"],
                                        label_visibility="collapsed", key="before_up")
        if before_file:
            before_bytes = before_file.read()
            if before_file.type in ("video/mp4","video/quicktime"):
                st.video(io.BytesIO(before_bytes))
            else:
                st.image(before_bytes, use_container_width=True)

    with up_a:
        st.markdown('<div style="color:#00FF87;font-size:10px;letter-spacing:3px;text-transform:uppercase;font-weight:700;margin-bottom:8px;">After</div>', unsafe_allow_html=True)
        after_file = st.file_uploader("after", type=["jpg","jpeg","png","mp4","mov"],
                                       label_visibility="collapsed", key="after_up")
        if after_file:
            after_bytes = after_file.read()
            if after_file.type in ("video/mp4","video/quicktime"):
                st.video(io.BytesIO(after_bytes))
            else:
                st.image(after_bytes, use_container_width=True)

    gap(16)
    both_uploaded = before_file and after_file
    run_compare = st.button("Compare Sessions ▶", use_container_width=True,
                             disabled=not both_uploaded, key="run_cmp")

    st.markdown('<hr>', unsafe_allow_html=True)

    if both_uploaded and run_compare:
        # Analyse both clips
        with st.spinner("Analysing Before session…"):
            res_before = analyze_media(
                file_bytes=before_bytes,
                file_type=before_file.type,
                position=cmp_position,
                play_type=cmp_play_type,
                age_group=cmp_age_group,
            )
        with st.spinner("Analysing After session…"):
            res_after = analyze_media(
                file_bytes=after_bytes,
                file_type=after_file.type,
                position=cmp_position,
                play_type=cmp_play_type,
                age_group=cmp_age_group,
            )

        if not res_before["success"] or not res_after["success"]:
            st.error("One or both analyses failed. Please try again.")
            st.stop()

        with st.spinner("Generating progress report…"):
            comparison = compare_sessions(res_before["data"], res_after["data"])

        if not comparison:
            st.error("Could not generate comparison. Please try again.")
            st.stop()

        with st.spinner("Generating coaching audio…"):
            cmp_audio = generate_comparison_audio(comparison)

        # ── Headline ──────────────────────────────────────────────────────────
        st.markdown(f"""
        <div style="border-left:3px solid #00FF87;padding:16px 24px;
                    background:#00FF870a;border-radius:0 10px 10px 0;margin-bottom:16px;">
            <div style="color:#00FF87;font-size:10px;letter-spacing:3px;
                        text-transform:uppercase;font-weight:700;margin-bottom:6px;">Progress Report</div>
            <div style="color:#ddd;font-size:15px;line-height:1.6;font-style:italic;">
                "{e(comparison.get('headline',''))}"
            </div>
        </div>
        """, unsafe_allow_html=True)

        if cmp_audio:
            st.markdown('<div style="color:#444;font-size:10px;letter-spacing:3px;text-transform:uppercase;font-weight:700;margin-bottom:6px;">🎙 Coach Feedback</div>', unsafe_allow_html=True)
            st.audio(cmp_audio, format="audio/mp3")
            gap(20)

        # ── Score delta table ──────────────────────────────────────────────────
        gap(8)
        label("Score Progression")
        deltas     = comparison.get("score_deltas", {})
        before_sc  = res_before["data"].get("scores", {})
        after_sc   = res_after["data"].get("scores", {})
        categories = [
            ("Technique",         "technique"),
            ("Body Position",     "body_position"),
            ("Spatial Awareness", "spatial_awareness"),
            ("Decision Making",   "decision_making"),
            ("Effort",            "effort"),
        ]
        st.markdown('<div style="background:#111;border:1.5px solid #1e1e1e;border-radius:14px;padding:20px 24px;">', unsafe_allow_html=True)
        for lbl, key in categories:
            bv    = before_sc.get(key, 5)
            av    = after_sc.get(key, 5)
            delta = deltas.get(key, av - bv)
            dc    = "#00FF87" if delta > 0 else "#FF4444" if delta < 0 else "#555"
            arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            sign  = "+" if delta > 0 else ""
            bpct  = bv * 10
            apct  = av * 10
            ac    = score_color(av)
            st.markdown(f"""
            <div style="margin-bottom:18px;">
                <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:7px;">
                    <span style="color:#666;font-size:11px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;">{e(lbl)}</span>
                    <div style="display:flex;align-items:center;gap:12px;">
                        <span style="color:#333;font-size:13px;">{bv}</span>
                        <span style="color:{dc};font-size:16px;font-weight:900;">{arrow} {sign}{delta}</span>
                        <span style="color:#fff;font-size:18px;font-weight:900;">{av}<span style="color:#2a2a2a;font-size:12px;font-weight:400;">/10</span></span>
                    </div>
                </div>
                <div style="position:relative;background:#1a1a1a;border-radius:3px;height:5px;overflow:hidden;">
                    <div style="width:{bpct}%;height:100%;background:#2a2a2a;border-radius:3px;position:absolute;"></div>
                    <div style="width:{apct}%;height:100%;background:{ac};border-radius:3px;position:absolute;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Improvements / Still needs work / Regression ───────────────────────
        gap(32)
        imp  = comparison.get("improvements", [])
        still = comparison.get("still_needs_work", [])
        reg  = comparison.get("regression", [])

        c1, c2 = st.columns(2, gap="medium")

        with c1:
            label("What Improved")
            st.markdown('<div style="background:#111;border:1.5px solid #00FF8730;border-radius:14px;padding:22px;">', unsafe_allow_html=True)
            for item in imp:
                st.markdown(f'<div style="color:#bbb;font-size:13px;line-height:1.6;padding:9px 0;border-bottom:1px solid #1a1a1a;display:flex;gap:10px;"><span style="color:#00FF87;flex-shrink:0;">↑</span>{e(item)}</div>', unsafe_allow_html=True)
            if not imp:
                st.markdown('<div style="color:#333;font-size:13px;">No measurable improvements yet — keep working.</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with c2:
            label("Still Needs Work")
            st.markdown('<div style="background:#111;border:1.5px solid #FFC70030;border-radius:14px;padding:22px;">', unsafe_allow_html=True)
            for item in still:
                st.markdown(f'<div style="color:#bbb;font-size:13px;line-height:1.6;padding:9px 0;border-bottom:1px solid #1a1a1a;display:flex;gap:10px;"><span style="color:#FFC700;flex-shrink:0;">→</span>{e(item)}</div>', unsafe_allow_html=True)
            if not still:
                st.markdown('<div style="color:#333;font-size:13px;">Everything is trending in the right direction.</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        if reg:
            gap(16)
            label("Flagged — Regression")
            st.markdown('<div style="background:#111;border:1.5px solid #FF444430;border-radius:14px;padding:22px;">', unsafe_allow_html=True)
            for item in reg:
                st.markdown(f'<div style="color:#bbb;font-size:13px;line-height:1.6;padding:9px 0;border-bottom:1px solid #1a1a1a;display:flex;gap:10px;"><span style="color:#FF4444;flex-shrink:0;">↓</span>{e(item)}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # ── Next session focus ─────────────────────────────────────────────────
        next_focus = comparison.get("next_session_focus", "")
        if next_focus:
            gap(32)
            label("Next Session Focus")
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#00FF8710,#00FF8705);
                        border:1.5px solid #00FF8740;border-radius:16px;padding:28px 32px;">
                <div style="color:#00FF87;font-size:10px;letter-spacing:3px;
                            text-transform:uppercase;font-weight:700;margin-bottom:10px;">★ One Thing</div>
                <div style="color:#fff;font-size:20px;font-weight:900;
                            line-height:1.3;letter-spacing:-0.5px;">{e(next_focus)}</div>
            </div>
            """, unsafe_allow_html=True)

        # ── Coach note ─────────────────────────────────────────────────────────
        note = comparison.get("coach_note", "")
        if note:
            gap(24)
            st.markdown(f"""
            <div style="background:#111;border:1.5px solid #1e1e1e;border-radius:14px;
                        padding:26px 32px;display:flex;gap:20px;align-items:flex-start;">
                <div style="font-size:28px;flex-shrink:0;">🎙</div>
                <div>
                    <div style="color:#444;font-size:10px;letter-spacing:3px;text-transform:uppercase;
                                font-weight:700;margin-bottom:10px;">Coach's Note</div>
                    <div style="color:#aaa;font-size:15px;line-height:1.7;font-style:italic;">"{e(note)}"</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    elif not both_uploaded:
        st.markdown("""
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                    height:200px;background:#111;border:1.5px dashed #1e1e1e;border-radius:14px;
                    text-align:center;padding:40px;">
            <div style="font-size:28px;margin-bottom:12px;opacity:0.2;">◎ ◎</div>
            <div style="color:#333;font-size:14px;font-weight:600;">
                Upload a Before clip and an After clip to compare sessions
            </div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Team Dashboard
# ══════════════════════════════════════════════════════════════════════════════

with tab_team:
    st.markdown("""
    <div style="color:#555;font-size:13px;line-height:1.7;margin-bottom:24px;">
        Upload clips for up to 5 players. Tactify will analyse each one individually,
        then identify the systemic weaknesses and strengths across your squad —
        and prescribe a single team drill to address the biggest gap.
    </div>
    """, unsafe_allow_html=True)

    # Shared context
    tm_ctx = st.columns(3, gap="medium")
    with tm_ctx[0]:
        label("Play Type")
        tm_play = st.selectbox("tm_play", PLAY_TYPES, index=8, label_visibility="collapsed", key="tm_play")
    with tm_ctx[1]:
        label("Age Group")
        tm_age  = st.selectbox("tm_age",  AGE_GROUPS, index=3, label_visibility="collapsed", key="tm_age")
    with tm_ctx[2]:
        label("Number of Players")
        tm_n    = st.selectbox("tm_n", [2, 3, 4, 5], index=1, label_visibility="collapsed", key="tm_n")

    gap(20)

    # Player slots
    SCORE_CATS = ["technique", "body_position", "spatial_awareness", "decision_making", "effort"]
    CAT_LABELS = ["Technique", "Body Position", "Spatial Awareness", "Decision Making", "Effort"]

    tm_slots = []
    slot_cols = st.columns(min(tm_n, 3), gap="medium")
    extra_cols = st.columns(tm_n - 3, gap="medium") if tm_n > 3 else []
    all_slot_cols = list(slot_cols) + list(extra_cols)

    for i in range(tm_n):
        with all_slot_cols[i]:
            pname = st.text_input(f"Player name", value=f"Player {i+1}",
                                  label_visibility="visible", key=f"tm_name_{i}")
            ppos  = st.selectbox("Position", POSITIONS, index=6,
                                  label_visibility="collapsed", key=f"tm_pos_{i}")
            pfile = st.file_uploader("Upload footage", type=["jpg","jpeg","png","mp4","mov"],
                                      label_visibility="collapsed", key=f"tm_file_{i}")
            if pfile:
                pb = pfile.read()
                if pfile.type in ("video/mp4","video/quicktime"):
                    st.video(io.BytesIO(pb))
                else:
                    st.image(pb, use_container_width=True)
                tm_slots.append({"name": pname, "position": ppos,
                                  "file": pfile, "bytes": pb})

    gap(16)
    enough = len(tm_slots) >= 2
    run_team = st.button("Analyze Squad ▶", use_container_width=True,
                          disabled=not enough, key="run_team")
    if not enough and tm_n > len(tm_slots):
        st.caption(f"Upload at least 2 player clips to run team analysis ({len(tm_slots)}/{tm_n} uploaded)")

    st.markdown('<hr>', unsafe_allow_html=True)

    if enough and run_team:
        # Analyse each player
        player_results = []
        prog = st.progress(0.0, text=f"Analysing {tm_slots[0]['name']}…")
        for idx, slot in enumerate(tm_slots):
            prog.progress((idx) / len(tm_slots), text=f"Analysing {slot['name']}… ({idx+1}/{len(tm_slots)})")
            with st.spinner(f"Analysing {slot['name']}…"):
                res = analyze_media(
                    file_bytes=slot["bytes"],
                    file_type=slot["file"].type,
                    position=slot["position"],
                    play_type=tm_play,
                    age_group=tm_age,
                )
            if res["success"]:
                player_results.append({"name": slot["name"], "data": res["data"]})
        prog.progress(1.0, text="Building team report…")

        with st.spinner("Identifying squad patterns…"):
            team_report = analyze_team_patterns(player_results)
        prog.empty()

        if not team_report:
            st.error("Could not generate team report. Please try again.")
            st.stop()

        # ── Team headline ──────────────────────────────────────────────────────
        st.markdown(f"""
        <div style="border-left:3px solid #00FF87;padding:16px 24px;
                    background:#00FF870a;border-radius:0 10px 10px 0;margin-bottom:32px;">
            <div style="color:#00FF87;font-size:10px;letter-spacing:3px;
                        text-transform:uppercase;font-weight:700;margin-bottom:6px;">
                Squad Assessment · {len(player_results)} Players
            </div>
            <div style="color:#ddd;font-size:15px;line-height:1.6;font-style:italic;">
                "{e(team_report.get('team_headline',''))}"
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Score heatmap ──────────────────────────────────────────────────────
        label("Squad Score Heatmap")
        # Build category averages
        cat_avgs = {}
        for cat in SCORE_CATS:
            vals = [pr["data"].get("scores", {}).get(cat, 5) for pr in player_results]
            cat_avgs[cat] = round(sum(vals) / len(vals), 1)

        # Header row
        header_cells = "".join(
            f'<div style="color:#444;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;'
            f'font-weight:700;text-align:center;padding:6px 4px;">{lbl}</div>'
            for lbl in CAT_LABELS
        )
        st.markdown(f"""
        <div style="background:#111;border:1.5px solid #1e1e1e;border-radius:14px;
                    padding:20px 24px;overflow-x:auto;">
            <div style="display:grid;grid-template-columns:120px repeat(5,1fr);gap:4px;min-width:600px;">
                <div></div>{header_cells}
        """, unsafe_allow_html=True)

        # Player rows
        for pr in player_results:
            sc = pr["data"].get("scores", {})
            name_cell = f'<div style="color:#666;font-size:12px;font-weight:600;padding:8px 4px;display:flex;align-items:center;">{e(pr["name"])}</div>'
            score_cells = ""
            for cat in SCORE_CATS:
                v  = sc.get(cat, 5)
                c  = score_color(v)
                score_cells += f"""
                <div style="background:{c}18;border:1px solid {c}40;border-radius:6px;
                            padding:8px 4px;text-align:center;">
                    <div style="color:{c};font-size:16px;font-weight:900;">{v}</div>
                </div>"""
            st.markdown(f'<div style="display:contents;">{name_cell}{score_cells}</div>',
                        unsafe_allow_html=True)

        # Team average row
        avg_cells = "".join(
            f'<div style="border-top:1px solid #2a2a2a;padding:10px 4px;text-align:center;">'
            f'<div style="color:#fff;font-size:14px;font-weight:900;">{cat_avgs[cat]}</div>'
            f'<div style="color:#333;font-size:9px;text-transform:uppercase;letter-spacing:1px;">avg</div></div>'
            for cat in SCORE_CATS
        )
        st.markdown(f"""
            <div style="display:contents;">
                <div style="border-top:1px solid #2a2a2a;padding:10px 4px;
                            color:#444;font-size:10px;letter-spacing:2px;
                            text-transform:uppercase;font-weight:700;display:flex;align-items:center;">
                    Team Avg
                </div>
                {avg_cells}
            </div>
            </div></div>
        """, unsafe_allow_html=True)

        # ── Systemic issues + strengths ────────────────────────────────────────
        gap(32)
        col_iss, col_str = st.columns(2, gap="medium")

        with col_iss:
            label("Systemic Issues")
            st.markdown('<div style="background:#111;border:1.5px solid #FF444430;border-radius:14px;padding:22px;">', unsafe_allow_html=True)
            for issue in team_report.get("systemic_issues", []):
                st.markdown(f'<div style="color:#bbb;font-size:13px;line-height:1.6;padding:9px 0;border-bottom:1px solid #1a1a1a;display:flex;gap:10px;"><span style="color:#FF4444;flex-shrink:0;margin-top:1px;">✗</span>{e(issue)}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with col_str:
            label("Squad Strengths")
            st.markdown('<div style="background:#111;border:1.5px solid #00FF8730;border-radius:14px;padding:22px;">', unsafe_allow_html=True)
            for strength in team_report.get("team_strengths", []):
                st.markdown(f'<div style="color:#bbb;font-size:13px;line-height:1.6;padding:9px 0;border-bottom:1px solid #1a1a1a;display:flex;gap:10px;"><span style="color:#00FF87;flex-shrink:0;margin-top:1px;">✓</span>{e(strength)}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # ── Recommended team drill ─────────────────────────────────────────────
        td = team_report.get("recommended_team_drill", {})
        if td:
            gap(32)
            label("Recommended Team Drill")
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#00FF8710,#00FF8705);
                        border:1.5px solid #00FF8740;border-radius:16px;padding:28px 32px;">
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap;">
                    <div style="color:#fff;font-size:18px;font-weight:900;">{e(td.get('name',''))}</div>
                    <span style="color:#00FF87;background:#00FF8715;border-radius:100px;
                                 padding:3px 12px;font-size:11px;font-weight:700;">⏱ {e(td.get('duration',''))}</span>
                    <span style="color:#444;background:#1a1a1a;border-radius:100px;
                                 padding:3px 12px;font-size:11px;">Targets: {e(team_report.get('weakest_category','').replace('_',' ').title())}</span>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;">
                    <div>
                        <div style="color:#444;font-size:10px;letter-spacing:2px;text-transform:uppercase;font-weight:700;margin-bottom:6px;">Setup</div>
                        <div style="color:#999;font-size:13px;line-height:1.6;">{e(td.get('setup',''))}</div>
                    </div>
                    <div>
                        <div style="color:#444;font-size:10px;letter-spacing:2px;text-transform:uppercase;font-weight:700;margin-bottom:6px;">Focus</div>
                        <div style="color:#999;font-size:13px;line-height:1.6;">{e(td.get('focus',''))}</div>
                    </div>
                    <div>
                        <div style="color:#00FF87;font-size:10px;letter-spacing:2px;text-transform:uppercase;font-weight:700;margin-bottom:6px;">You know it's working when</div>
                        <div style="color:#999;font-size:13px;line-height:1.6;">{e(td.get('know_its_working',''))}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # ── Individual player cards ────────────────────────────────────────────
        gap(32)
        label("Individual Player Notes")
        notes = team_report.get("individual_notes", [])
        p_cols = st.columns(min(len(notes), 3), gap="medium")
        for i, (col, note) in enumerate(zip(p_cols * 2, notes[:5])):
            with col:
                pname = e(note.get("player", f"Player {i+1}"))
                sc    = player_results[i]["data"].get("scores", {}) if i < len(player_results) else {}
                vals  = [sc.get(k, 5) for k in SCORE_CATS]
                avg   = round(sum(vals) / max(len(vals), 1), 1)
                oc    = score_color(avg)
                st.markdown(f"""
                <div style="background:#111;border:1.5px solid #1e1e1e;border-radius:14px;padding:20px;">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px;">
                        <div style="color:#fff;font-weight:800;font-size:15px;">{pname}</div>
                        <div style="font-size:26px;font-weight:900;color:{oc};line-height:1;">{avg}</div>
                    </div>
                    <div style="margin-bottom:10px;">
                        <div style="color:#00FF87;font-size:10px;letter-spacing:2px;text-transform:uppercase;font-weight:700;margin-bottom:4px;">Top Strength</div>
                        <div style="color:#888;font-size:12px;line-height:1.5;">{e(note.get('top_strength',''))}</div>
                    </div>
                    <div>
                        <div style="color:#FF4444;font-size:10px;letter-spacing:2px;text-transform:uppercase;font-weight:700;margin-bottom:4px;">Priority Fix</div>
                        <div style="color:#888;font-size:12px;line-height:1.5;">{e(note.get('priority_fix',''))}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    elif not enough:
        st.markdown("""
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                    height:200px;background:#111;border:1.5px dashed #1e1e1e;border-radius:14px;
                    text-align:center;padding:40px;">
            <div style="font-size:28px;margin-bottom:12px;opacity:0.2;">◎ ◎ ◎</div>
            <div style="color:#333;font-size:14px;font-weight:600;">
                Upload at least 2 player clips to run team analysis
            </div>
        </div>
        """, unsafe_allow_html=True)
