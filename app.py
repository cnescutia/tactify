"""
Tactify — AI Soccer Coaching Platform
Nike/Adidas lab aesthetic: pure black, neon green, bold editorial typography.
"""

import os
import sys

# ── Streamlit must be imported first so errors can be surfaced in the UI ──────
import streamlit as st
import streamlit.components.v1 as st_components
st.set_page_config(
    page_title="Tactify · AI Soccer Coaching",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)
try:
    import base64
    import html as _html
    import io
    import json as _json
    import urllib.parse
    import zlib
    from datetime import datetime

    import anthropic as _anthropic
    import plotly.graph_objects as go
    from dotenv import load_dotenv

    from knowledge_base import POSITIONS, PLAY_TYPES, AGE_GROUPS
    from analyzer import (analyze_media, generate_coaching_audio, generate_training_plan,
                           compare_sessions,
                           generate_comparison_audio, analyze_team_patterns,
                           merge_audio_into_video, create_annotated_video_simple,
                           extract_moment_clip)
    from pdf_report import generate_pdf_report

    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=True)

    # ── Monetization layer (graceful import — app works without paywall) ──────
    try:
        from db_client import get_or_create_user, increment_analyses, check_can_analyze
        from auth import render_auth_gate, render_paywall, check_session_upgrade
        _MONETIZATION_ENABLED = True
    except Exception:
        _MONETIZATION_ENABLED = False
        def get_or_create_user(email):
            return {"email": email, "analyses_used": 0, "is_pro": False,
                    "stripe_customer_id": None}
        def increment_analyses(email):
            return -1
        def check_can_analyze(email):
            return (True, "")
        def render_auth_gate():
            return None
        def render_paywall(email, analyses_used):
            return False
        def check_session_upgrade(email):
            return False

except Exception as _import_error:
    st.error(f"**Startup import failed** (Python {sys.version}):\n\n```\n{_import_error}\n```")
    st.stop()

# ── Page config ───────────────────────────────────────────────────────────────



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

/* ─ Camera input ─ */
[data-testid="stCameraInput"] {
    background: #111 !important;
    border: 1.5px dashed #2a2a2a !important;
    border-radius: 12px !important;
}
[data-testid="stCameraInput"] button {
    background: #00FF87 !important;
    color: #0a0a0a !important;
    border-radius: 8px !important;
    font-weight: 800 !important;
}

/* ─ Progress bar ─ */
[data-testid="stProgressBar"] > div > div {
    background: #00FF87 !important;
}

/* ─ Chat input ─ */
[data-testid="stChatInput"] textarea {
    background: #111 !important;
    border: 1.5px solid #1e1e1e !important;
    color: #fff !important;
    border-radius: 10px !important;
}
[data-testid="stChatMessageContent"] {
    background: #111 !important;
    border: 1px solid #1e1e1e !important;
    border-radius: 10px !important;
}

/* ─ Mobile responsive ─ */
@media (max-width: 768px) {
    .main .block-container { padding: 0 1rem 4rem !important; }
    [data-testid="stHorizontalBlock"] { flex-direction: column !important; }
    [data-testid="stHorizontalBlock"] > div { width: 100% !important; min-width: 100% !important; }
    .stTabs [data-baseweb="tab"] { padding: 10px 12px !important; font-size: 9px !important; }
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


# ── Section: Radar Chart ──────────────────────────────────────────────────────

def render_radar_chart(scores: dict):
    keys  = ["technique", "body_position", "spatial_awareness", "decision_making", "effort"]
    cats  = ["Technique", "Body Position", "Spatial\nAwareness", "Decision\nMaking", "Effort"]
    vals  = [scores.get(k, 0) for k in keys]
    vals_c = vals + [vals[0]]
    cats_c = cats + [cats[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals_c,
        theta=cats_c,
        fill="toself",
        fillcolor="rgba(0,255,135,0.10)",
        line=dict(color="#00FF87", width=2),
        marker=dict(size=7, color="#00FF87"),
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True, range=[0, 10],
                gridcolor="#1e1e1e", linecolor="#1e1e1e",
                tickfont=dict(color="#444", size=9),
                tickvals=[2, 4, 6, 8, 10],
            ),
            angularaxis=dict(
                gridcolor="#1e1e1e", linecolor="#2a2a2a",
                tickfont=dict(color="#888", size=11),
            ),
            bgcolor="#0a0a0a",
        ),
        paper_bgcolor="#0a0a0a",
        margin=dict(l=30, r=30, t=30, b=30),
        showlegend=False,
        height=300,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ── Section: Stat Card PNG ─────────────────────────────────────────────────────

def generate_stat_card_png(scores: dict, position: str, age_group: str, summary: str = "") -> bytes | None:
    try:
        from PIL import Image, ImageDraw, ImageFont
        W, H = 1080, 1080
        img = Image.new("RGB", (W, H), (10, 10, 10))
        d = ImageDraw.Draw(img)

        # Background grid lines
        for i in range(0, W, 60):
            d.line([(i, 0), (i, H)], fill=(20, 20, 20), width=1)
        for i in range(0, H, 60):
            d.line([(0, i), (W, i)], fill=(20, 20, 20), width=1)

        # Accent border
        d.rectangle([0, 0, W-1, H-1], outline=(0, 255, 135), width=3)
        d.rectangle([8, 8, W-9, H-9], outline=(30, 30, 30), width=1)

        # Try to load a font, fallback to default
        try:
            font_big   = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 120)
            font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72)
            font_med   = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 38)
            font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
            font_xs    = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        except Exception:
            font_big = font_title = font_med = font_small = font_xs = ImageFont.load_default()

        # TACTIFY header
        d.text((54, 54), "TACTIFY", font=font_title, fill=(255, 255, 255))
        d.text((54, 140), "AI SOCCER COACHING PLATFORM", font=font_xs, fill=(60, 60, 60))

        # Neon line separator
        d.rectangle([54, 178, W-54, 181], fill=(0, 255, 135))

        # Overall score
        keys = ["technique", "body_position", "spatial_awareness", "decision_making", "effort"]
        vals = [scores.get(k, 5) for k in keys]
        overall = round(sum(vals) / len(vals), 1)
        oc = (0, 255, 135) if overall >= 8 else (255, 199, 0) if overall >= 6 else (255, 68, 68)

        d.text((54, 210), str(overall), font=font_big, fill=oc)
        d.text((54, 345), "OVERALL SCORE", font=font_xs, fill=(80, 80, 80))

        # Position badge
        pos_short = position.split("(")[-1].rstrip(")") if "(" in position else position[:10]
        d.rectangle([W-300, 210, W-54, 300], fill=(20, 20, 20), outline=(0, 255, 135), width=2)
        d.text((W-280, 232), pos_short, font=font_med, fill=(0, 255, 135))

        # Category bars
        bar_labels = ["TECHNIQUE", "BODY POS.", "SPATIAL", "DECISIONS", "EFFORT"]
        bar_keys   = ["technique", "body_position", "spatial_awareness", "decision_making", "effort"]
        bar_y = 420
        for i, (lbl, key) in enumerate(zip(bar_labels, bar_keys)):
            v   = scores.get(key, 5)
            c   = (0, 255, 135) if v >= 8 else (255, 199, 0) if v >= 6 else (255, 68, 68)
            y   = bar_y + i * 88
            d.text((54, y), lbl, font=font_xs, fill=(100, 100, 100))
            d.text((W-140, y), f"{v}/10", font=font_med, fill=c)
            # Track
            d.rectangle([54, y+36, W-54, y+52], fill=(25, 25, 25))
            # Fill
            fill_w = int((W - 108) * v / 10)
            d.rectangle([54, y+36, 54+fill_w, y+52], fill=c)

        # Summary snippet
        if summary:
            d.rectangle([54, H-170, W-54, H-54], fill=(18, 18, 18))
            snippet = summary[:100] + ("…" if len(summary) > 100 else "")
            d.text((70, H-152), f'"{snippet}"', font=font_xs, fill=(120, 120, 120))

        # Date footer
        d.text((54, H-38), datetime.now().strftime("%B %d, %Y"), font=font_xs, fill=(40, 40, 40))
        d.text((W-280, H-38), "tactify.app", font=font_xs, fill=(40, 40, 40))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


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

# ── Auth gate (sidebar) ───────────────────────────────────────────────────────
_user_email = render_auth_gate()

# ── Load user record from Supabase (if email provided) ───────────────────────
_user_record = {"email": _user_email or "", "analyses_used": 0, "is_pro": False, "stripe_customer_id": None}
if _user_email:
    try:
        _user_record = get_or_create_user(_user_email)
    except Exception:
        pass

    # Check for Stripe payment redirect on page load
    check_session_upgrade(_user_email)

# ── Sidebar: plan status badge ────────────────────────────────────────────────
if _user_email:
    _is_pro = _user_record.get("is_pro", False)
    _analyses_used = _user_record.get("analyses_used", 0)
    with st.sidebar:
        if _is_pro:
            st.markdown(
                """
                <div style="background:#00FF8715;border:1px solid #00FF8740;
                            border-radius:8px;padding:8px 14px;text-align:center;
                            margin-bottom:8px;">
                    <span style="color:#00FF87;font-size:12px;font-weight:800;
                                 letter-spacing:1px;">Pro</span>
                    <span style="color:#555;font-size:11px;margin-left:4px;">Unlimited analyses</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            _free_label = f"Free  {_analyses_used}/1 analyses used"
            st.markdown(
                f"""
                <div style="background:#1a1a1a;border:1px solid #2a2a2a;
                            border-radius:8px;padding:8px 14px;text-align:center;
                            margin-bottom:8px;">
                    <span style="color:#666;font-size:11px;font-weight:700;
                                 letter-spacing:0.5px;">{_free_label}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

# ── Session history (persists across reruns) ──────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "coach_messages" not in st.session_state:
    st.session_state.coach_messages = []
if "coach_context" not in st.session_state:
    st.session_state.coach_context = None
if "demo_active" not in st.session_state:
    st.session_state.demo_active = False

# ── Mode Tabs ─────────────────────────────────────────────────────────────────

# ── No-email prompt ───────────────────────────────────────────────────────────
if not _user_email:
    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                min-height:40vh;padding:60px 20px;text-align:center;">
        <div style="font-size:52px;margin-bottom:20px;">⚽</div>
        <div style="color:#fff;font-size:28px;font-weight:900;letter-spacing:-0.5px;margin-bottom:12px;">
            Welcome to Tactify
        </div>
        <div style="color:#444;font-size:15px;line-height:1.7;max-width:420px;margin-bottom:32px;">
            Enter your email in the sidebar to get started with AI-powered soccer coaching.
        </div>
        <div style="background:#00FF8715;border:1.5px solid #00FF8740;border-radius:12px;
                    padding:16px 28px;color:#00FF87;font-size:13px;font-weight:700;
                    letter-spacing:1px;">
            Open the sidebar  →  Enter your email  →  Run your first analysis free
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

tab_single, tab_compare, tab_team = st.tabs(["Single Session", "Before / After Comparison", "Team Dashboard"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Single Session
# ══════════════════════════════════════════════════════════════════════════════

with tab_single:
    # Demo mode button
    _demo_col, _reset_col, _ = st.columns([1.4, 0.8, 2])
    with _demo_col:
        _demo_mode = st.button("▶ Try Demo  — no upload needed", use_container_width=True)
    with _reset_col:
        if st.session_state.get("demo_active"):
            if st.button("✕ Exit Demo", use_container_width=True):
                st.session_state["demo_active"] = False
                st.rerun()
    if _demo_mode:
        st.session_state["demo_active"] = True
        st.rerun()

    col_up, col_ctx = st.columns([1.5, 1], gap="large")

    with col_up:
        # ── Input mode toggle ─────────────────────────────────────────────────
        _input_mode = st.radio(
            "input_mode",
            ["📁  Upload File", "📷  Webcam Capture"],
            horizontal=True,
            label_visibility="collapsed",
        )
        gap(8)

        uploaded_file  = None
        webcam_capture = None
        file_bytes     = None

        if _input_mode == "📁  Upload File":
            label("Upload Footage")
            uploaded_file = st.file_uploader(
                "footage",
                type=["jpg", "jpeg", "png", "mp4", "mov"],
                label_visibility="collapsed",
            )
            if uploaded_file:
                # Show a lightweight preview — do NOT read bytes here to avoid memory issues
                is_video = uploaded_file.type in ("video/mp4", "video/quicktime")
                file_size_mb = uploaded_file.size / (1024 * 1024)
                if is_video:
                    st.markdown(
                        f'<div style="background:#111;border:1.5px solid #00FF8740;border-radius:10px;'
                        f'padding:16px 20px;color:#00FF87;font-size:13px;font-weight:700;">'
                        f'✓ Video ready · {file_size_mb:.1f} MB — click Run Analysis to start</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    file_bytes = uploaded_file.read()
                    st.image(file_bytes, use_container_width=True)
        else:
            label("Webcam Capture")
            st.markdown(
                '<div style="color:#555;font-size:12px;margin-bottom:8px;">Point camera at player · hit Capture · then Run Analysis</div>',
                unsafe_allow_html=True,
            )
            webcam_capture = st.camera_input("Capture frame", label_visibility="collapsed")
            if webcam_capture:
                file_bytes = webcam_capture.read()
                st.image(file_bytes, use_container_width=True)

    with col_ctx:
        label("Analysis Context")
        position  = st.selectbox("Position",  POSITIONS,  index=6,  label_visibility="collapsed")
        play_type = st.selectbox("Play Type", PLAY_TYPES, index=8,  label_visibility="collapsed")
        age_group = st.selectbox("Age Group", AGE_GROUPS, index=3,  label_visibility="collapsed")
        notes     = st.text_area("Notes", height=80, label_visibility="collapsed",
                                  placeholder="e.g. right-footed striker, focus on off-ball movement…")
        label("Coaching Tone")
        _tone = st.select_slider(
            "tone",
            options=["🟢 Encouraging", "⚖️ Balanced", "🔴 Demanding"],
            value="⚖️ Balanced",
            label_visibility="collapsed",
        )
        st.session_state["coaching_tone"] = _tone
        label("Coaching Persona")
        _persona = st.selectbox(
            "persona",
            ["⚽ Expert Coach (Default)", "🔴 Jürgen Klopp — Intense & Emotional", "🔵 Pep Guardiola — Tactical & Positional", "⚫ José Mourinho — Direct & Results-Focused"],
            label_visibility="collapsed",
            key="coaching_persona",
        )
        label("Output Language")
        _language = st.selectbox(
            "language",
            ["🇬🇧 English", "🇪🇸 Spanish", "🇧🇷 Portuguese", "🇫🇷 French", "🇩🇪 German", "🇮🇹 Italian"],
            label_visibility="collapsed",
            key="output_language",
        )
        gap(10)
        _has_input = bool(uploaded_file or webcam_capture)
        run = st.button("Run Analysis ▶", use_container_width=True, disabled=not _has_input)

    st.markdown('<hr>', unsafe_allow_html=True)

    # ── Demo mode — render pre-built analysis ─────────────────────────────────
    if st.session_state.get("demo_active") and not (_has_input and run):
        _DEMO = {
            "summary": "Technically gifted winger with excellent acceleration but consistently drops the shoulder too early on 1v1s, telegraphing the dribble direction to defenders. Body position on receiving is upright — limiting first-touch control and quick turn capability.",
            "scores": {"technique": 7, "body_position": 5, "spatial_awareness": 8, "decision_making": 6, "effort": 9},
            "annotations": [
                {"number": 1, "label": "Shoulder drop — telegraphed", "note": "Left shoulder drops 0.4s before the cut, giving the defender a clear read on the direction.", "region": "upper_body", "severity": "error", "frame": 2, "x_pct": 0.42, "y_pct": 0.28},
                {"number": 2, "label": "Upright first touch", "note": "Receiving posture is vertical — hips high, no knee bend — killing the ability to turn quickly.", "region": "hips", "severity": "warning", "frame": 1, "x_pct": 0.48, "y_pct": 0.52},
                {"number": 3, "label": "Strong side scan missing", "note": "No head check in the 2.0s before receiving — blind to the overlapping full-back in space.", "region": "head", "severity": "warning", "frame": 1, "x_pct": 0.46, "y_pct": 0.12},
                {"number": 4, "label": "Plant foot — good width", "note": "Consistent wide plant foot placement creates a solid base for crossing actions.", "region": "left_foot", "severity": "strength", "frame": 3, "x_pct": 0.38, "y_pct": 0.84},
                {"number": 5, "label": "Explosive first step", "note": "First stride after the touch covers 1.8m — elite acceleration profile for this age group.", "region": "left_leg", "severity": "strength", "frame": 3, "x_pct": 0.40, "y_pct": 0.68},
            ],
            "priority_fix": {
                "title": "Disguise the shoulder before cutting",
                "what": "The left shoulder drops and rotates toward the intended cut direction 0.4 seconds before the foot plant — any professional defender reads this instantly.",
                "why": "At senior level this costs you the 1v1 every time. Defenders are trained to watch the hips and shoulders, not the ball. An early shoulder drop is the equivalent of announcing your pass.",
                "cue": "Shoulders flat, then explode",
                "drill": {
                    "name": "Mirror Wall Cuts",
                    "duration": "12 min",
                    "setup": "Stand 1m from a wall mirror. Cone at your feet. Practice 10 cuts per side, watching your own shoulder in the mirror. Shoulder must stay level until the plant foot hits.",
                    "focus": "Keep both shoulders parallel to the ground until the last possible moment",
                    "know_its_working": "You can no longer predict which way you'll go just by watching your own shoulders in the mirror"
                }
            },
            "fix_cards": [
                {"mistake": "Upright receiving posture", "why_it_matters": "High hips = slow turn. At professional pace you lose 0.3–0.5 seconds on every first touch, enough for a press to arrive.", "correction": "Bend knees to 120° as the ball travels to you. Weight on the balls of your feet, not heels. Hips below shoulder height on contact.", "cue": "Low hips, live feet",
                 "drill": {"name": "Low Gate Receive", "duration": "10 min", "setup": "Set two cones 40cm high (use poles or a low hurdle). Receive the ball only if you can pass under the gate with your hips. Partner passes from 8m.", "know_its_working": "You feel your quads burning on every receive — that means your hips are low enough"}},
                {"mistake": "No pre-receive scan", "why_it_matters": "Missing the overlapping run means you play into pressure instead of into space — your team loses a 2v1 advantage.", "correction": "Make two head checks in the final 3 seconds before the ball reaches you. Look over both shoulders, not just the strong side.", "cue": "Check twice, touch once",
                 "drill": {"name": "Numbered Scanner", "duration": "8 min", "setup": "Coach holds up finger numbers (1–5) behind you. Scan, call the number, then receive. 20 reps each side.", "know_its_working": "You can call the number correctly 9 out of 10 times without breaking your run shape"}},
            ],
            "strengths": [
                "Explosive first stride — covers 1.8m in the first step after contact, elite acceleration profile",
                "Wide plant foot placement creates a consistent crossing base — rare technical consistency",
                "High effort press recovery — averages 3.2 pressing actions per minute of footage"
            ],
            "best_moment": {"frame": 3, "description": "Perfect wide plant foot position on the cross — weight transferred correctly, non-kicking foot pointing at the target, contact made through the lower half of the ball."},
            "worst_moment": {"frame": 2, "what": "Shoulder telegraphing the cut direction", "cause": "Early shoulder rotation before plant foot is set — a habit from youth training where defenders were slower", "effect": "Defender steps to the correct side 0.4s before the cut — the dribble is neutralised before it starts"},
            "pro_reference": {"player": "Leroy Sané", "team": "Bayern Munich", "note": "Sané keeps his shoulders square until the absolute last moment on cuts, making him unreadable even at elite defensive pace. His ability to cut either way from the same body shape is the exact technical quality to study.", "youtube_query": "Leroy Sané dribbling technique shoulder body feint analysis"},
            "key_frames": [],
        }
        _demo_position = "Winger (RW/LW)"
        _demo_age = "U21 / Youth"
        # ── Demo banner ────────────────────────────────────────────────────────
        st.markdown("""
        <div style="background:#FFC70015;border:1.5px solid #FFC70040;border-radius:12px;padding:14px 22px;margin-bottom:24px;display:flex;align-items:center;gap:12px;">
            <span style="font-size:20px;">⚡</span>
            <div>
                <div style="color:#FFC700;font-size:10px;letter-spacing:3px;font-weight:700;text-transform:uppercase;">Demo Analysis</div>
                <div style="color:#888;font-size:12px;">Pre-loaded winger session · Upload your own footage to run a live AI analysis</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        # ── Summary ────────────────────────────────────────────────────────────
        st.markdown(f"""
        <div style="border-left:3px solid #00FF87;padding:16px 24px;background:#00FF870a;border-radius:0 10px 10px 0;margin-bottom:24px;">
            <div style="color:#00FF87;font-size:10px;letter-spacing:3px;text-transform:uppercase;font-weight:700;margin-bottom:6px;">AI Assessment</div>
            <div style="color:#ddd;font-size:15px;line-height:1.6;font-style:italic;">"{e(_DEMO['summary'])}"</div>
        </div>
        """, unsafe_allow_html=True)
        # ── Scores ─────────────────────────────────────────────────────────────
        _dc1, _dc2 = st.columns([1, 1], gap="large")
        with _dc1:
            label("Performance Scores")
            render_scores(_DEMO["scores"])
        with _dc2:
            label("Skill Radar")
            render_radar_chart(_DEMO["scores"])
        gap(24)
        # ── Priority fix ────────────────────────────────────────────────────────
        label("Priority Focus This Session")
        render_priority_fix(_DEMO["priority_fix"])
        gap(24)
        # ── Fix cards ───────────────────────────────────────────────────────────
        label("Fix Cards · Mistakes & Drills")
        render_fix_cards(_DEMO["fix_cards"])
        gap(24)
        # ── Strengths ───────────────────────────────────────────────────────────
        label("What You're Doing Well")
        st.markdown('<div style="background:#111;border:1.5px solid #00FF8730;border-radius:14px;padding:22px;">', unsafe_allow_html=True)
        for _s in _DEMO["strengths"]:
            st.markdown(f'<div style="color:#bbb;font-size:13px;line-height:1.6;padding:9px 0;border-bottom:1px solid #1a1a1a;display:flex;gap:10px;"><span style="color:#00FF87;flex-shrink:0;margin-top:1px;">✓</span>{e(_s)}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        gap(24)
        # ── Pro reference ────────────────────────────────────────────────────────
        label("Professional Reference")
        render_pro_reference(_DEMO["pro_reference"])
        st.stop()

    # ── Results (single session) ───────────────────────────────────────────────

    if _has_input and run:
        # ── Auth gate check ────────────────────────────────────────────────────
        if not _user_email:
            st.warning("Please enter your email in the sidebar to run an analysis.")
            st.stop()

        # ── Paywall check ──────────────────────────────────────────────────────
        _can_analyze, _paywall_reason = check_can_analyze(_user_email)
        if not _can_analyze:
            _fresh_record = get_or_create_user(_user_email)
            render_paywall(_user_email, _fresh_record.get("analyses_used", 0))
            st.stop()

        # Read file bytes now (deferred from preview to avoid memory issues on upload)
        if uploaded_file and file_bytes is None:
            file_bytes = uploaded_file.read()

        # Webcam captures are always JPEG images; file uploads can be video
        if webcam_capture:
            is_video   = False
            file_type  = "image/jpeg"
        else:
            is_video   = uploaded_file.type in ("video/mp4", "video/quicktime")
            file_type  = uploaded_file.type

        # Safe filename stem for downloads
        if webcam_capture:
            _fname_stem = "webcam_capture"
        else:
            _fname_stem = uploaded_file.name.rsplit(".", 1)[0]

        # ── Progress bar ───────────────────────────────────────────────────────
        _prog = st.progress(0, text="⚽  Initializing AI analysis engine…")

        # ── Step 1: Claude analysis ────────────────────────────────────────────
        _prog.progress(10, text="⚽  Feeding footage to Claude Vision AI…")
        result = analyze_media(
            file_bytes=file_bytes,
            file_type=file_type,
            position=position,
            play_type=play_type,
            age_group=age_group,
            additional_notes=notes,
            coaching_persona=_persona,
            output_language=_language,
        )

        if not result["success"]:
            _prog.empty()
            st.error(f"Analysis failed: {result['error']}")
            st.stop()

        data        = result["data"]
        annotations = data.get("annotations", [])
        scores      = data.get("scores", {})
        summary     = e(data.get("summary", ""))

        # Save to session history
        st.session_state.history.append({
            "session": len(st.session_state.history) + 1,
            "timestamp": datetime.now().strftime("%H:%M"),
            "position": position,
            "scores": dict(scores),
            "summary": data.get("summary", ""),
        })
        # Reset chat context for new analysis
        st.session_state.coach_messages = []
        st.session_state.coach_context = data

        # ── Step 2: Coaching audio ────────────────────────────────────────────
        _prog.progress(45, text="🎙  Generating expert coaching voice…")
        try:
            audio_bytes = generate_coaching_audio(data, position)
        except Exception as _ae:
            audio_bytes = None

        # ── Step 3: Annotate video + merge audio + extract key clips ───────────
        final_video = None
        annotated_video = None   # visual-only; used in HTML player
        best_clip   = None
        worst_clip  = None
        num_kf      = len(result.get("key_frames", [])) or 4
        if is_video:
            try:
                _video_size_mb = len(file_bytes) / (1024 * 1024)
                # Downscale large videos to 720p before annotation to prevent OOM
                _annotate_bytes = file_bytes
                if _video_size_mb > 10:
                    _prog.progress(55, text="📐  Optimising video resolution…")
                    from analyzer import _downscale_video
                    _annotate_bytes = _downscale_video(file_bytes, max_height=720)
                _prog.progress(60, text="🎬  Painting coaching overlay frame by frame…")
                annotated_video = create_annotated_video_simple(
                    _annotate_bytes, annotations, scores,
                    skeleton=data.get("skeleton"),
                )
                base_video = annotated_video if annotated_video else file_bytes
                if audio_bytes:
                    _prog.progress(75, text="🔊  Syncing coaching audio to video…")
                    merged = merge_audio_into_video(base_video, audio_bytes)
                    final_video = merged if merged else base_video
                else:
                    final_video = base_video
            except Exception as _ve:
                final_video = file_bytes
                annotated_video = file_bytes

            # ── Extract best / worst moment clips (skip for large videos) ──
            best_fn  = data.get("best_moment",  {}).get("frame", 1)
            worst_fn = data.get("worst_moment", {}).get("frame", 1)
            try:
                _prog.progress(88, text="✂️  Cutting best & worst moment clips…")
                best_clip  = extract_moment_clip(_annotate_bytes, best_fn,  num_kf)
                worst_clip = extract_moment_clip(_annotate_bytes, worst_fn, num_kf)
            except Exception:
                pass

        _prog.progress(100, text="🏆  Analysis complete — let's get to work!")
        _prog.empty()

        # ── Record analysis usage ──────────────────────────────────────────────
        if _user_email:
            try:
                increment_analyses(_user_email)
            except Exception:
                pass

        # ── Summary banner ─────────────────────────────────────────────────────
        sum_col, aud_col = st.columns([1.6, 1], gap="large")
        with sum_col:
            st.markdown(f"""
            <div style="border-left:3px solid #00FF87;padding:16px 24px;
                        background:#00FF870a;border-radius:0 10px 10px 0;margin-bottom:16px;">
                <div style="color:#00FF87;font-size:10px;letter-spacing:3px;
                            text-transform:uppercase;font-weight:700;margin-bottom:6px;">AI Assessment</div>
                <div style="color:#ddd;font-size:15px;line-height:1.6;font-style:italic;">"{summary}"</div>
            </div>
            """, unsafe_allow_html=True)
        with aud_col:
            # For images show auto-playing audio; for videos it's synced in HTML player below
            if audio_bytes and not is_video:
                st.markdown(
                    '<div style="color:#444;font-size:10px;letter-spacing:3px;'
                    'text-transform:uppercase;font-weight:700;margin-bottom:8px;">🎙 Coaching Audio</div>',
                    unsafe_allow_html=True,
                )
                _aud_b64 = base64.b64encode(audio_bytes).decode()
                st_components.html(f"""
<audio id="coach_audio" controls autoplay style="width:100%;margin-top:4px;">
  <source src="data:audio/mp3;base64,{_aud_b64}" type="audio/mp3">
</audio>
<script>
  document.getElementById('coach_audio').volume = 0.85;
</script>
""", height=60)

        gap(8)
        _copy_summary = data.get("summary", "")
        _copy_txt = f"Tactify Analysis\n\nSummary: {_copy_summary}\n\nScores: " + " | ".join(f"{k.replace('_',' ').title()}: {v}/10" for k,v in data.get('scores',{}).items())
        st_components.html(f"""
        <button onclick="navigator.clipboard.writeText({repr(_copy_txt)}).then(()=>{{
            this.textContent='✓ Copied!';
            setTimeout(()=>{{this.textContent='📋 Copy Summary';}},2000);
        }})" style="background:transparent;color:#555;border:1px solid #2a2a2a;border-radius:6px;
            padding:6px 14px;font-size:11px;font-weight:600;letter-spacing:1px;
            text-transform:uppercase;cursor:pointer;font-family:-apple-system,sans-serif;">
            📋 Copy Summary
        </button>
        """, height=44)

        # ── Media + Scores ─────────────────────────────────────────────────────
        col_media, col_scores = st.columns([1.2, 1], gap="large")

        with col_media:
            if is_video:
                label("Coaching Video — Press Play")
                _play_video = annotated_video if annotated_video else (final_video or file_bytes)
                _vid_size   = len(_play_video) if _play_video else 0
                _use_sync   = bool(audio_bytes and _play_video and _vid_size < 25 * 1024 * 1024)
                if _use_sync:
                    st.markdown(
                        '<div style="color:#555;font-size:11px;letter-spacing:1px;margin-bottom:8px;">'
                        'Audio coaching narration plays automatically · dots and arrows show focus areas</div>',
                        unsafe_allow_html=True,
                    )
                    _vid_b64 = base64.b64encode(_play_video).decode()
                    _aud_b64 = base64.b64encode(audio_bytes).decode()
                    st_components.html(f"""
<div style="border-radius:10px;overflow:hidden;background:#000;">
  <video id="tac_v" controls style="width:100%;display:block;max-height:420px;">
    <source src="data:video/mp4;base64,{_vid_b64}" type="video/mp4">
  </video>
  <audio id="tac_a">
    <source src="data:audio/mp3;base64,{_aud_b64}" type="audio/mp3">
  </audio>
</div>
<script>
(function(){{
  var v=document.getElementById('tac_v'), a=document.getElementById('tac_a');
  function sync(){{ a.currentTime=v.currentTime; }}
  v.addEventListener('play',     function(){{ sync(); a.play(); }});
  v.addEventListener('pause',    function(){{ a.pause(); }});
  v.addEventListener('seeked',   function(){{ sync(); if(!v.paused) a.play(); }});
  v.addEventListener('ended',    function(){{ a.pause(); a.currentTime=0; }});
  v.addEventListener('ratechange', function(){{ a.playbackRate=v.playbackRate; }});
}})();
</script>
""", height=460)
                else:
                    # Fallback: large video or no audio — use native player
                    st.markdown(
                        '<div style="color:#555;font-size:11px;letter-spacing:1px;margin-bottom:8px;">'
                        'Coaching audio embedded · dots and arrows show focus areas</div>',
                        unsafe_allow_html=True,
                    )
                    st.video(final_video if final_video else file_bytes)
                    if audio_bytes:
                        st.audio(audio_bytes, format="audio/mp3")

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
                gap(8)
                render_radar_chart(scores)

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

            # ── Best / Worst moment video clips ────────────────────────────────
            if is_video and (best_clip or worst_clip):
                gap(16)
                clip_cols = st.columns(2, gap="large")
                _CLIP_STYLE = (
                    "font-size:9px;letter-spacing:3px;font-weight:700;"
                    "text-transform:uppercase;margin-bottom:8px;"
                )
                with clip_cols[0]:
                    if best_clip:
                        st.markdown(
                            f'<div style="color:#00FF87;{_CLIP_STYLE}">Best Moment</div>',
                            unsafe_allow_html=True,
                        )
                        st.video(best_clip)
                with clip_cols[1]:
                    if worst_clip:
                        st.markdown(
                            f'<div style="color:#EF4444;{_CLIP_STYLE}">Worst Moment</div>',
                            unsafe_allow_html=True,
                        )
                        st.video(worst_clip)

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

        # ── Injury Risk ───────────────────────────────────────────────────────
        gap(32)
        label("Injury Risk Assessment")
        from analyzer import _assess_injury_risk
        _risks = _assess_injury_risk(data)
        _risk_colors = {"high": "#FF4444", "medium": "#FFC700", "clear": "#00FF87", "low": "#00FF87"}
        st.markdown('<div style="background:#111;border:1.5px solid #1e1e1e;border-radius:14px;padding:20px 24px;">', unsafe_allow_html=True)
        for _r in _risks:
            _rc = _risk_colors.get(_r["level"], "#FFC700")
            st.markdown(f"""
            <div style="display:flex;gap:16px;padding:13px 0;border-bottom:1px solid #1a1a1a;align-items:flex-start;">
                <span style="font-size:24px;flex-shrink:0;">{_r['icon']}</span>
                <div style="flex:1;">
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
                        <span style="color:#fff;font-weight:700;font-size:13px;">{e(_r['area'])}</span>
                        <span style="background:{_rc}20;color:{_rc};font-size:9px;font-weight:700;
                                     letter-spacing:2px;text-transform:uppercase;padding:2px 8px;
                                     border-radius:100px;border:1px solid {_rc}40;">{_r['level'].upper()}</span>
                    </div>
                    <div style="color:#555;font-size:13px;line-height:1.55;">{e(_r['note'])}</div>
                </div>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── 7-Day Training Plan ────────────────────────────────────────────────────
        gap(32)
        label("7-Day Training Plan")
        with st.spinner("Building your personalised training week…"):
            _plan = generate_training_plan(data, position, age_group)
        if _plan:
            st.markdown(f"""
            <div style="background:#00FF8710;border:1.5px solid #00FF8740;border-radius:14px;padding:20px 26px;margin-bottom:20px;">
                <div style="color:#00FF87;font-size:10px;letter-spacing:3px;text-transform:uppercase;font-weight:700;margin-bottom:6px;">Week Goal</div>
                <div style="color:#fff;font-size:16px;font-weight:800;">{e(_plan.get('week_goal',''))}</div>
            </div>
            """, unsafe_allow_html=True)
            _day_cols = st.columns(7, gap="small")
            _day_colors = {{"rest": "#1a1a1a", "active": "#111"}}
            for _dc, _day in zip(_day_cols, _plan.get("days", [])):
                with _dc:
                    _is_rest = _day.get("rest", False)
                    _border = "#333" if _is_rest else "#00FF8740"
                    _drills_html = "".join(
                        f'<div style="color:#888;font-size:10px;padding:3px 0;border-bottom:1px solid #1a1a1a;">'
                        f'⚡ {e(d.get("name",""))}<br>'
                        f'<span style="color:#555">{e(d.get("duration",""))}</span></div>'
                        for d in _day.get("drills", [])[:3]
                    )
                    st.markdown(f"""
                    <div style="background:#111;border:1.5px solid {_border};border-radius:10px;padding:12px 10px;min-height:160px;">
                        <div style="color:#00FF87;font-size:9px;letter-spacing:2px;text-transform:uppercase;font-weight:700;margin-bottom:4px;">{e(_day.get('day',''))}</div>
                        <div style="color:{'#444' if _is_rest else '#fff'};font-size:11px;font-weight:700;margin-bottom:6px;">{'Rest' if _is_rest else e(_day.get('focus',''))}</div>
                        {'<div style="color:#444;font-size:11px;">Recovery day</div>' if _is_rest else _drills_html}
                    </div>
                    """, unsafe_allow_html=True)

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
        label("Downloads")
        dl_cols = st.columns([1, 1, 1, 1])

        # PDF scouting report (primary download)
        with dl_cols[0]:
            _pdf_bytes = generate_pdf_report(
                data,
                result.get("key_frames", []),
                position,
                age_group,
            )
            if _pdf_bytes:
                st.download_button(
                    "⬇ PDF Scouting Report",
                    data=_pdf_bytes,
                    file_name=f"tactify_report_{_fname_stem}.pdf",
                    mime="application/pdf",
                )
            else:
                report_html = build_report_card_html(data, result.get("key_frames", []), position, age_group)
                st.download_button(
                    "⬇ Player Report Card",
                    data=report_html,
                    file_name=f"tactify_report_{_fname_stem}.html",
                    mime="text/html",
                )

        # Stat card PNG download
        with dl_cols[1]:
            _card_png = generate_stat_card_png(scores, position, age_group, data.get("summary", ""))
            if _card_png:
                st.download_button(
                    "⬇ Player Stat Card",
                    data=_card_png,
                    file_name=f"tactify_statcard_{_fname_stem}.png",
                    mime="image/png",
                )

        if is_video and final_video:
            with dl_cols[2]:
                st.download_button(
                    "⬇ Coaching Video",
                    data=final_video,
                    file_name=f"tactify_coached_{_fname_stem}.mp4",
                    mime="video/mp4",
                )
        if audio_bytes:
            with dl_cols[3]:
                st.download_button(
                    "⬇ Coaching Audio",
                    data=audio_bytes,
                    file_name=f"tactify_audio_{_fname_stem}.mp3",
                    mime="audio/mp3",
                )

        # ── Share ──────────────────────────────────────────────────────────────
        gap(16)
        label("Share Report")
        _share_summary = data.get("summary", "")
        _share_scores  = data.get("scores", {})
        _overall_share = round(sum(_share_scores.values()) / max(len(_share_scores), 1), 1)
        _share_text    = (
            f"⚽ Tactify AI Coaching Report\n\n"
            f"Overall Score: {_overall_share}/10\n"
            f"Key Finding: {_share_summary[:200]}...\n\n"
            f"Priority Fix: {data.get('priority_fix', {}).get('title', '')}\n\n"
            f"Generated by Tactify — AI Soccer Coaching"
        )
        import urllib.parse as _up
        _wa_url    = f"https://wa.me/?text={_up.quote(_share_text)}"
        _email_url = f"mailto:?subject={_up.quote('Tactify Coaching Report')}&body={_up.quote(_share_text)}"
        _sh1, _sh2, _sh3 = st.columns([1, 1, 2])
        with _sh1:
            st.markdown(f"""
            <a href="{_wa_url}" target="_blank" style="
                display:flex;align-items:center;justify-content:center;gap:8px;
                background:#25D366;color:#fff;text-decoration:none;
                padding:10px 16px;border-radius:8px;font-size:12px;
                font-weight:700;letter-spacing:1px;text-transform:uppercase;">
                📱 WhatsApp
            </a>""", unsafe_allow_html=True)
        with _sh2:
            st.markdown(f"""
            <a href="{_email_url}" style="
                display:flex;align-items:center;justify-content:center;gap:8px;
                background:transparent;color:#00FF87;text-decoration:none;
                border:1.5px solid #00FF87;padding:10px 16px;border-radius:8px;
                font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">
                ✉️ Email
            </a>""", unsafe_allow_html=True)

        # ── Progress Dashboard ──────────────────────────────────────────────────
        if len(st.session_state.history) > 1:
            gap(40)
            label("Progress Tracker · Session History")
            # Streak badge
            _streak = len(st.session_state.history)
            _latest_avg = round(sum(st.session_state.history[-1]["scores"].get(k,5) for k in ["technique","body_position","spatial_awareness","decision_making","effort"])/5,1) if st.session_state.history else 0
            _prev_avg = round(sum(st.session_state.history[-2]["scores"].get(k,5) for k in ["technique","body_position","spatial_awareness","decision_making","effort"])/5,1) if len(st.session_state.history)>1 else 0
            _trend = "📈" if _latest_avg > _prev_avg else "📉" if _latest_avg < _prev_avg else "➡️"
            st.markdown(f"""
<div style="display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap;">
    <div style="background:#111;border:1.5px solid #00FF8740;border-radius:10px;padding:12px 20px;display:flex;align-items:center;gap:10px;">
        <span style="font-size:24px;">🔥</span>
        <div>
            <div style="color:#00FF87;font-size:18px;font-weight:900;">{_streak} Session{'s' if _streak!=1 else ''}</div>
            <div style="color:#444;font-size:10px;letter-spacing:2px;text-transform:uppercase;">Streak</div>
        </div>
    </div>
    <div style="background:#111;border:1.5px solid #1e1e1e;border-radius:10px;padding:12px 20px;display:flex;align-items:center;gap:10px;">
        <span style="font-size:24px;">{_trend}</span>
        <div>
            <div style="color:#fff;font-size:18px;font-weight:900;">{_latest_avg}</div>
            <div style="color:#444;font-size:10px;letter-spacing:2px;text-transform:uppercase;">Latest Avg</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
            _hist = st.session_state.history
            _categories = [
                ("Technique",         "technique"),
                ("Body Position",     "body_position"),
                ("Spatial Awareness", "spatial_awareness"),
                ("Decision Making",   "decision_making"),
                ("Effort",            "effort"),
            ]
            _sessions = [h["session"] for h in _hist]
            _colors = ["#00FF87", "#FFC700", "#00BFFF", "#FF6B6B", "#B06EFF"]
            fig_hist = go.Figure()
            for (cat_label, cat_key), color in zip(_categories, _colors):
                fig_hist.add_trace(go.Scatter(
                    x=_sessions,
                    y=[h["scores"].get(cat_key, 5) for h in _hist],
                    mode="lines+markers",
                    name=cat_label,
                    line=dict(color=color, width=2),
                    marker=dict(size=8, color=color),
                ))
            fig_hist.update_layout(
                paper_bgcolor="#0a0a0a",
                plot_bgcolor="#0d0d0d",
                xaxis=dict(
                    title="Session", gridcolor="#1a1a1a", linecolor="#1e1e1e",
                    tickfont=dict(color="#555"), titlefont=dict(color="#555"),
                    tickvals=_sessions,
                ),
                yaxis=dict(
                    title="Score", range=[0, 10], gridcolor="#1a1a1a", linecolor="#1e1e1e",
                    tickfont=dict(color="#555"), titlefont=dict(color="#555"),
                ),
                legend=dict(
                    bgcolor="#111", bordercolor="#1e1e1e", borderwidth=1,
                    font=dict(color="#888", size=11),
                ),
                margin=dict(l=50, r=20, t=20, b=40),
                height=320,
            )
            st.plotly_chart(fig_hist, use_container_width=True, config={"displayModeBar": False})

        # ── Ask the Coach ───────────────────────────────────────────────────────
        gap(40)
        st.markdown("""
        <div style="border-left:3px solid #00FF87;padding:12px 20px;background:#00FF870a;
                    border-radius:0 10px 10px 0;margin-bottom:20px;">
            <div style="color:#00FF87;font-size:10px;letter-spacing:3px;text-transform:uppercase;
                        font-weight:700;margin-bottom:4px;">Ask the Coach</div>
            <div style="color:#555;font-size:13px;">
                Chat with your AI coach about this analysis — ask about scores, drills, technique, anything.
            </div>
        </div>
        """, unsafe_allow_html=True)

        for _msg in st.session_state.coach_messages:
            with st.chat_message(_msg["role"]):
                st.write(_msg["content"])

        if _chat_input := st.chat_input("Ask your coach anything about this analysis…"):
            st.session_state.coach_messages.append({"role": "user", "content": _chat_input})
            with st.chat_message("user"):
                st.write(_chat_input)
            with st.chat_message("assistant"):
                with st.spinner("Coach thinking…"):
                    try:
                        _client = _anthropic.Anthropic()
                        _ctx = _json.dumps(st.session_state.coach_context or data, indent=2)
                        _resp = _client.messages.create(
                            model="claude-sonnet-4-6",
                            max_tokens=1024,
                            system=(
                                f"You are an expert soccer coach called Coach AI on the Tactify platform. "
                                f"You have just analyzed footage of a {position} player. "
                                f"Here is the full analysis data:\n{_ctx}\n\n"
                                f"Answer questions in a direct, motivating coaching style. "
                                f"Keep responses concise (2-4 sentences) and always actionable."
                            ),
                            messages=[{"role": m["role"], "content": m["content"]}
                                      for m in st.session_state.coach_messages],
                        )
                        _answer = _resp.content[0].text
                    except Exception as _ce:
                        _answer = f"Coach unavailable right now: {_ce}"
                    st.write(_answer)
                    st.session_state.coach_messages.append({"role": "assistant", "content": _answer})

    elif not _has_input:
        gap(16)
        st.markdown("""
        <div style="background:#0d0d0d;border:1px solid #1a1a1a;border-radius:16px;padding:40px 36px;margin-bottom:24px;">
            <div style="font-size:10px;color:#00FF87;letter-spacing:4px;font-weight:700;
                        text-transform:uppercase;margin-bottom:20px;">What Tactify Does</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;">
                <div style="background:#111;border:1px solid #1e1e1e;border-radius:12px;padding:20px;">
                    <div style="font-size:22px;margin-bottom:10px;">🧠</div>
                    <div style="color:#fff;font-size:13px;font-weight:700;margin-bottom:6px;">Claude Vision Analysis</div>
                    <div style="color:#555;font-size:12px;line-height:1.6;">
                        6-frame AI breakdown of body position, decision-making, technique, and spatial awareness.
                    </div>
                </div>
                <div style="background:#111;border:1px solid #1e1e1e;border-radius:12px;padding:20px;">
                    <div style="font-size:22px;margin-bottom:10px;">🎯</div>
                    <div style="color:#fff;font-size:13px;font-weight:700;margin-bottom:6px;">Live Annotation Overlay</div>
                    <div style="color:#555;font-size:12px;line-height:1.6;">
                        Dots, arrows, and callouts track the player frame-by-frame with motion-aware positioning.
                    </div>
                </div>
                <div style="background:#111;border:1px solid #1e1e1e;border-radius:12px;padding:20px;">
                    <div style="font-size:22px;margin-bottom:10px;">🎙</div>
                    <div style="color:#fff;font-size:13px;font-weight:700;margin-bottom:6px;">Neural Coaching Voice</div>
                    <div style="color:#555;font-size:12px;line-height:1.6;">
                        Auto-plays an expert coaching narration the moment analysis completes.
                    </div>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;margin-top:20px;">
                <div style="background:#111;border:1px solid #1e1e1e;border-radius:12px;padding:20px;">
                    <div style="font-size:22px;margin-bottom:10px;">📊</div>
                    <div style="color:#fff;font-size:13px;font-weight:700;margin-bottom:6px;">Radar + Progress Charts</div>
                    <div style="color:#555;font-size:12px;line-height:1.6;">
                        Spider chart of all scores. Multi-session progress tracker shows improvement over time.
                    </div>
                </div>
                <div style="background:#111;border:1px solid #1e1e1e;border-radius:12px;padding:20px;">
                    <div style="font-size:22px;margin-bottom:10px;">💬</div>
                    <div style="color:#fff;font-size:13px;font-weight:700;margin-bottom:6px;">Ask the Coach Chat</div>
                    <div style="color:#555;font-size:12px;line-height:1.6;">
                        Chat with Claude about your analysis. Ask anything — drills, scores, technique fixes.
                    </div>
                </div>
                <div style="background:#111;border:1px solid #1e1e1e;border-radius:12px;padding:20px;">
                    <div style="font-size:22px;margin-bottom:10px;">📄</div>
                    <div style="color:#fff;font-size:13px;font-weight:700;margin-bottom:6px;">PDF + Stat Card Export</div>
                    <div style="color:#555;font-size:12px;line-height:1.6;">
                        Professional scouting report PDF and a shareable 1080×1080 player stat card PNG.
                    </div>
                </div>
            </div>
        </div>

        <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
            <div style="display:flex;align-items:center;gap:8px;">
                <div style="width:6px;height:6px;border-radius:50%;background:#00FF87;box-shadow:0 0 6px #00FF87;"></div>
                <span style="color:#444;font-size:12px;letter-spacing:1px;">MP4 · MOV · JPG · PNG</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px;">
                <div style="width:6px;height:6px;border-radius:50%;background:#00FF87;box-shadow:0 0 6px #00FF87;"></div>
                <span style="color:#444;font-size:12px;letter-spacing:1px;">Or use your webcam — no file needed</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px;">
                <div style="width:6px;height:6px;border-radius:50%;background:#00FF87;box-shadow:0 0 6px #00FF87;"></div>
                <span style="color:#444;font-size:12px;letter-spacing:1px;">Results in ~20 seconds</span>
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
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                padding:80px 40px;text-align:center;">
        <div style="font-size:48px;margin-bottom:24px;">🏟️</div>
        <div style="color:#fff;font-size:28px;font-weight:900;letter-spacing:-0.5px;margin-bottom:12px;">
            Team Dashboard
        </div>
        <div style="color:#333;font-size:14px;max-width:400px;line-height:1.7;margin-bottom:32px;">
            Analyse your full squad, spot systemic weaknesses, and get a team drill targeting your biggest gap.
        </div>
        <div style="background:#00FF8720;border:1.5px solid #00FF8760;border-radius:100px;
                    padding:10px 28px;color:#00FF87;font-size:12px;font-weight:700;letter-spacing:2px;
                    text-transform:uppercase;">
            Coming Soon
        </div>
    </div>
    """, unsafe_allow_html=True)



