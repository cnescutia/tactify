"""
pdf_report.py — Professional dark-background PDF scouting report for Tactify.
Nike/Adidas lab aesthetic: pure black (#0a0a0a), neon green (#00FF87), bold editorial.
"""
from __future__ import annotations

import io
import os
import tempfile
from datetime import datetime


# ── Colour palette ─────────────────────────────────────────────────────────────
BG      = (10,  10,  10)
PANEL   = (20,  20,  20)
CARD    = (26,  26,  26)
ACCENT  = (0,  255, 135)
WHITE   = (240, 240, 240)
GRAY    = (160, 160, 160)
DIM     = ( 80,  80,  80)
WARN    = (245, 158,  11)
ERR     = (239,  68,  68)
BLACK   = (10,  10,  10)


def _s(text, fallback: str = "") -> str:
    """Encode text as latin-1 safe string for fpdf2 core fonts."""
    if not text:
        return fallback
    return str(text).encode("latin-1", errors="replace").decode("latin-1")


def _score_color(v: float):
    return ACCENT if v >= 8 else WARN if v >= 6 else ERR


def _fill(pdf, color):
    pdf.set_fill_color(*color)


def _text(pdf, color):
    pdf.set_text_color(*color)


def _draw(pdf, color):
    pdf.set_draw_color(*color)


def _bg_rect(pdf, x, y, w, h, color=None):
    _fill(pdf, color or PANEL)
    pdf.rect(x, y, w, h, style="F")


def _bar(pdf, x, y, w, h, pct: float, color):
    """Draw a progress bar: dark track + colored fill."""
    _fill(pdf, (30, 30, 30))
    pdf.rect(x, y, w, h, style="F")
    if pct > 0:
        _fill(pdf, color)
        pdf.rect(x, y, w * min(pct, 1.0), h, style="F")


def _h_line(pdf, y: float, x1: float = 14, x2: float = None):
    W = 210
    _draw(pdf, (35, 35, 35))
    pdf.set_line_width(0.25)
    pdf.line(x1, y, x2 or W - 14, y)


def generate_pdf_report(
    data: dict,
    key_frames: list,
    position: str,
    age_group: str,
    club_name: str = "",
) -> bytes | None:
    """
    Generate a two-page professional PDF scouting report.
    Page 1 — executive summary (scores, key frame, priority fix)
    Page 2 — drill prescriptions + strengths + pro reference
    Returns PDF bytes or None if fpdf2 is unavailable.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        return None

    scores    = data.get("scores", {})
    SCORE_META = [
        ("Technique",        "technique"),
        ("Body Position",    "body_position"),
        ("Spatial Aware.",   "spatial_awareness"),
        ("Decision Making",  "decision_making"),
        ("Effort",           "effort"),
    ]
    vals    = [scores.get(k, 5) for _, k in SCORE_META]
    overall = round(sum(vals) / max(len(vals), 1), 1)

    pf        = data.get("priority_fix", {})
    fix_cards = data.get("fix_cards", [])[:3]
    best      = data.get("best_moment", {})
    worst     = data.get("worst_moment", {})
    strengths = data.get("strengths", [])
    ref       = data.get("pro_reference", {})
    summary   = _s(data.get("summary", ""), "Analysis complete.")
    annotations = data.get("annotations", [])

    W, H = 210, 297  # A4 mm

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(0, 0, 0)
    pdf.set_auto_page_break(auto=False)

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 1 — Executive Summary
    # ══════════════════════════════════════════════════════════════════════════
    pdf.add_page()

    # Background
    _bg_rect(pdf, 0, 0, W, H, BG)

    # Top accent stripe
    _fill(pdf, ACCENT)
    pdf.rect(0, 0, W, 2.5, style="F")

    # ── Header ────────────────────────────────────────────────────────────────
    y = 7
    pdf.set_xy(14, y)
    pdf.set_font("Helvetica", "B", 22)
    _text(pdf, ACCENT)
    pdf.cell(70, 10, "TACTIFY", ln=False)

    pdf.set_xy(14, y + 11)
    pdf.set_font("Helvetica", "", 7)
    _text(pdf, DIM)
    pdf.cell(70, 4, "AI SOCCER COACHING REPORT", ln=False)

    # Right: date / position / club
    pdf.set_xy(110, y)
    pdf.set_font("Helvetica", "B", 8)
    _text(pdf, DIM)
    pdf.cell(86, 4, datetime.now().strftime("%B %d, %Y").upper(), align="R", ln=True)

    pdf.set_xy(110, y + 5)
    pdf.set_font("Helvetica", "B", 12)
    _text(pdf, WHITE)
    pdf.cell(86, 6, position.upper(), align="R", ln=True)

    pdf.set_xy(110, y + 12)
    pdf.set_font("Helvetica", "", 8)
    _text(pdf, DIM)
    meta_right = age_group.upper()
    if club_name:
        meta_right += f"  -  {club_name.upper()}"
    pdf.cell(86, 4, meta_right, align="R", ln=True)

    y = 24
    _h_line(pdf, y)

    # ── Overall score badge + summary ─────────────────────────────────────────
    y = 29
    oc = _score_color(overall)

    # Badge
    _fill(pdf, oc)
    pdf.rect(14, y, 22, 22, style="F")
    pdf.set_xy(14, y + 2)
    pdf.set_font("Helvetica", "B", 18)
    _text(pdf, BLACK)
    pdf.cell(22, 10, str(overall), align="C", ln=True)
    pdf.set_xy(14, y + 13)
    pdf.set_font("Helvetica", "B", 6)
    pdf.cell(22, 4, "OVERALL", align="C", ln=False)

    # Summary quote
    _bg_rect(pdf, 40, y, W - 54, 22, PANEL)
    pdf.set_xy(44, y + 4)
    pdf.set_font("Helvetica", "I", 10)
    _text(pdf, GRAY)
    pdf.multi_cell(W - 62, 5.5, f'"{summary}"')

    y = 56

    # ── Left col: worst moment frame  |  Right col: score bars ───────────────
    COL1_X, COL1_W = 14, 110
    COL2_X, COL2_W = 130, 66

    IMG_H = 62  # mm tall for image

    # Image
    img_path = None
    frame_idx = max(0, worst.get("frame", 1) - 1)
    if key_frames and frame_idx < len(key_frames):
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
                tf.write(key_frames[frame_idx])
                img_path = tf.name
            pdf.image(img_path, x=COL1_X, y=y, w=COL1_W, h=IMG_H)
        except Exception:
            pass
        finally:
            if img_path and os.path.exists(img_path):
                try:
                    os.unlink(img_path)
                except OSError:
                    pass

    # "Worst moment" caption strip
    _bg_rect(pdf, COL1_X, y + IMG_H - 10, COL1_W, 10, (8, 8, 8))
    pdf.set_xy(COL1_X + 3, y + IMG_H - 8)
    pdf.set_font("Helvetica", "B", 6.5)
    _text(pdf, ERR)
    pdf.cell(30, 3.5, "WORST MOMENT", ln=False)
    if worst.get("what"):
        pdf.set_xy(COL1_X + 3, y + IMG_H - 4.5)
        pdf.set_font("Helvetica", "", 6.5)
        _text(pdf, GRAY)
        pdf.cell(COL1_W - 6, 3.5, _s(worst["what"])[:68], ln=False)

    # Score bars (right column)
    sy = y
    pdf.set_xy(COL2_X, sy)
    pdf.set_font("Helvetica", "B", 7)
    _text(pdf, DIM)
    pdf.cell(COL2_W, 4, "PERFORMANCE SCORES", ln=True)
    sy += 6

    for lbl, key in SCORE_META:
        v   = scores.get(key, 5)
        c   = _score_color(v)
        pdf.set_xy(COL2_X, sy)
        pdf.set_font("Helvetica", "", 7.5)
        _text(pdf, GRAY)
        pdf.cell(COL2_W - 12, 4, lbl, ln=False)
        pdf.set_font("Helvetica", "B", 8)
        _text(pdf, WHITE)
        pdf.set_xy(COL2_X + COL2_W - 12, sy)
        pdf.cell(12, 4, f"{v}/10", align="R", ln=False)
        sy += 5
        _bar(pdf, COL2_X, sy, COL2_W, 2.5, v / 10, c)
        sy += 6

    y = y + IMG_H + 5

    # ── Priority Fix ──────────────────────────────────────────────────────────
    _h_line(pdf, y)
    y += 5

    if pf:
        # Label
        pdf.set_xy(14, y)
        pdf.set_font("Helvetica", "B", 7)
        _text(pdf, DIM)
        pdf.cell(80, 4, "PRIORITY FIX THIS SESSION", ln=False)
        y += 6

        # Title
        pdf.set_xy(14, y)
        pdf.set_font("Helvetica", "B", 13)
        _text(pdf, ACCENT)
        pdf.multi_cell(W - 28, 7, _s(pf.get("title", "")).upper())
        y = pdf.get_y() + 2

        # What / Why two-column cards
        card_w = (W - 32) // 2
        for ci, (field, header) in enumerate([("what", "THE PROBLEM"), ("why", "WHY IT COSTS YOU")]):
            cx = 14 + ci * (card_w + 4)
            _bg_rect(pdf, cx, y, card_w, 22, CARD)
            pdf.set_xy(cx + 3, y + 2)
            pdf.set_font("Helvetica", "B", 6.5)
            _text(pdf, ACCENT)
            pdf.cell(card_w - 6, 4, header, ln=True)
            pdf.set_xy(cx + 3, y + 7)
            pdf.set_font("Helvetica", "", 7.5)
            _text(pdf, GRAY)
            pdf.multi_cell(card_w - 6, 4.2, _s(pf.get(field, ""))[:160])
        y += 26

        # Cue pill
        if pf.get("cue"):
            _fill(pdf, ACCENT)
            pdf.rect(14, y, W - 28, 8, style="F")
            pdf.set_xy(14, y + 1.5)
            pdf.set_font("Helvetica", "B", 9)
            _text(pdf, BLACK)
            pdf.cell(W - 28, 5, f'CUE: "{_s(pf["cue"])}"', align="C", ln=False)
            y += 12

    # ── Annotation quick list ─────────────────────────────────────────────────
    if annotations:
        _h_line(pdf, y)
        y += 4
        pdf.set_xy(14, y)
        pdf.set_font("Helvetica", "B", 7)
        _text(pdf, DIM)
        pdf.cell(0, 4, f"COACHING ANNOTATIONS  -  {len(annotations[:5])} FOCUS AREAS", ln=True)
        y += 6

        SEV_C = {"strength": ACCENT, "warning": WARN, "error": ERR}
        cols = 2
        ann_w = (W - 32) // cols
        for ai, ann in enumerate(annotations[:4]):
            cx = 14 + (ai % cols) * (ann_w + 4)
            ay = y if ai < cols else y + 14
            c  = SEV_C.get(ann.get("severity", "warning"), WARN)
            # dot
            _fill(pdf, c)
            pdf.rect(cx, ay + 2, 3, 3, style="F")
            pdf.set_xy(cx + 5, ay)
            pdf.set_font("Helvetica", "B", 7.5)
            _text(pdf, (*(c), ))  # fpdf2 ignores alpha — use tuple
            pdf.cell(ann_w - 5, 4, _s(ann.get("label", ""))[:34], ln=True)
            pdf.set_xy(cx + 5, ay + 4.5)
            pdf.set_font("Helvetica", "", 6.5)
            _text(pdf, GRAY)
            pdf.cell(ann_w - 5, 3.5, _s(ann.get("note", ""))[:70], ln=False)
        y += 28

    # ── Footer ────────────────────────────────────────────────────────────────
    _fill(pdf, ACCENT)
    pdf.rect(0, H - 7, W, 7, style="F")
    pdf.set_xy(14, H - 5.5)
    pdf.set_font("Helvetica", "B", 7)
    _text(pdf, BLACK)
    pdf.cell(100, 5, "TACTIFY - AI SOCCER COACHING", ln=False)
    pdf.set_xy(110, H - 5.5)
    pdf.set_font("Helvetica", "", 7)
    pdf.cell(86, 5, "Powered by Claude AI  -  tactify.ai", align="R", ln=False)

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 2 — Drill Cards + Strengths + Pro Reference
    # ══════════════════════════════════════════════════════════════════════════
    pdf.add_page()
    _bg_rect(pdf, 0, 0, W, H, BG)
    _fill(pdf, ACCENT)
    pdf.rect(0, 0, W, 2.5, style="F")

    y = 10
    pdf.set_xy(14, y)
    pdf.set_font("Helvetica", "B", 14)
    _text(pdf, WHITE)
    pdf.cell(100, 7, "TRAINING PRESCRIPTION", ln=False)
    pdf.set_xy(14, y + 9)
    pdf.set_font("Helvetica", "", 8)
    _text(pdf, DIM)
    pdf.cell(100, 4, "Drills - Corrections - Professional Reference", ln=False)
    pdf.set_xy(130, y + 2)
    pdf.set_font("Helvetica", "B", 10)
    _text(pdf, ACCENT)
    pdf.cell(66, 5, position.upper(), align="R", ln=False)

    y = 22
    _h_line(pdf, y)
    y += 6

    # ── Priority Drill (full width) ────────────────────────────────────────────
    drill_p = pf.get("drill", {}) if pf else {}
    if drill_p.get("name"):
        pdf.set_xy(14, y)
        pdf.set_font("Helvetica", "B", 7)
        _text(pdf, ACCENT)
        pdf.cell(0, 4, "PRIORITY DRILL", ln=True)
        y += 6

        _bg_rect(pdf, 14, y, W - 28, 46, CARD)

        # Drill name
        pdf.set_xy(18, y + 3)
        pdf.set_font("Helvetica", "B", 13)
        _text(pdf, WHITE)
        pdf.cell(W - 36, 7, _s(drill_p["name"]), ln=True)

        # Duration + setup row
        if drill_p.get("duration"):
            pdf.set_xy(18, y + 11)
            _fill(pdf, ACCENT)
            dur_w = len(_s(drill_p["duration"])) * 2 + 8
            pdf.rect(18, y + 11, dur_w, 6, style="F")
            pdf.set_xy(18, y + 11.5)
            pdf.set_font("Helvetica", "B", 7.5)
            _text(pdf, BLACK)
            pdf.cell(dur_w, 5, f" {_s(drill_p['duration'])} ", ln=False)

        pdf.set_xy(18, y + 20)
        pdf.set_font("Helvetica", "B", 7)
        _text(pdf, DIM)
        pdf.cell(W - 36, 4, "SETUP", ln=True)
        pdf.set_xy(18, y + 25)
        pdf.set_font("Helvetica", "", 8)
        _text(pdf, GRAY)
        pdf.multi_cell(W - 36, 4.5, _s(drill_p.get("setup", ""))[:220])

        if drill_p.get("know_its_working"):
            pdf.set_xy(18, y + 38)
            pdf.set_font("Helvetica", "B", 7)
            _text(pdf, ACCENT)
            pdf.cell(30, 4, "+ IT'S WORKING WHEN: ", ln=False)
            pdf.set_font("Helvetica", "", 7)
            _text(pdf, GRAY)
            pdf.cell(W - 66, 4, _s(drill_p["know_its_working"])[:90], ln=False)

        y += 52

    # ── Fix Cards grid ────────────────────────────────────────────────────────
    if fix_cards:
        pdf.set_xy(14, y)
        pdf.set_font("Helvetica", "B", 7)
        _text(pdf, DIM)
        pdf.cell(0, 4, f"FIX CARDS  -  {len(fix_cards)} COACHING CORRECTIONS", ln=True)
        y += 6

        card_w  = (W - 28 - (len(fix_cards) - 1) * 5) // len(fix_cards)
        card_h  = 58
        SEV_C   = {"strength": ACCENT, "warning": WARN, "error": ERR}

        for ci, card in enumerate(fix_cards):
            cx   = 14 + ci * (card_w + 5)
            sev  = card.get("severity", "warning")
            c    = SEV_C.get(sev, WARN)
            dr   = card.get("drill", {})

            # Card body
            _bg_rect(pdf, cx, y, card_w, card_h, CARD)

            # Color header strip
            _fill(pdf, c)
            pdf.rect(cx, y, card_w, 7, style="F")
            pdf.set_xy(cx + 3, y + 1)
            pdf.set_font("Helvetica", "B", 7.5)
            _text(pdf, BLACK)
            pdf.cell(card_w - 6, 5, _s(card.get("mistake", f"Fix {ci+1}"))[:28].upper(), ln=False)

            # Why
            pdf.set_xy(cx + 3, y + 10)
            pdf.set_font("Helvetica", "B", 6.5)
            _text(pdf, DIM)
            pdf.cell(card_w - 6, 3.5, "WHY IT MATTERS", ln=True)
            pdf.set_xy(cx + 3, y + 14.5)
            pdf.set_font("Helvetica", "", 7)
            _text(pdf, GRAY)
            pdf.multi_cell(card_w - 6, 3.8, _s(card.get("why_it_matters", ""))[:130])

            # Correction
            pdf.set_xy(cx + 3, y + 31)
            pdf.set_font("Helvetica", "B", 6.5)
            _text(pdf, DIM)
            pdf.cell(card_w - 6, 3.5, "CORRECTION", ln=True)
            pdf.set_xy(cx + 3, y + 35.5)
            pdf.set_font("Helvetica", "", 7)
            _text(pdf, GRAY)
            pdf.multi_cell(card_w - 6, 3.8, _s(card.get("correction", ""))[:110])

            # Cue
            if card.get("cue"):
                _fill(pdf, (30, 30, 30))
                pdf.rect(cx + 3, y + card_h - 16, card_w - 6, 7, style="F")
                pdf.set_xy(cx + 3, y + card_h - 15)
                pdf.set_font("Helvetica", "B", 7.5)
                _text(pdf, c)
                pdf.cell(card_w - 6, 5, f'"{_s(card["cue"])}"', align="C", ln=False)

            # Drill
            if dr.get("name"):
                pdf.set_xy(cx + 3, y + card_h - 8)
                pdf.set_font("Helvetica", "", 6.5)
                _text(pdf, DIM)
                ds = f"DRILL: {_s(dr['name'])}"
                if dr.get("duration"):
                    ds += f"  -  {_s(dr['duration'])}"
                pdf.cell(card_w - 6, 4, ds[:40], ln=False)

        y += card_h + 8

    # ── Strengths ─────────────────────────────────────────────────────────────
    _h_line(pdf, y)
    y += 5

    col_str_w = (W - 32) // 2

    if strengths:
        pdf.set_xy(14, y)
        pdf.set_font("Helvetica", "B", 7)
        _text(pdf, DIM)
        pdf.cell(col_str_w, 4, "STRENGTHS", ln=True)
        y += 5

        for s in strengths[:3]:
            sy = pdf.get_y()
            if sy > H - 55:
                break
            _fill(pdf, ACCENT)
            pdf.rect(14, sy + 2, 2.5, 2.5, style="F")
            pdf.set_xy(19, sy)
            pdf.set_font("Helvetica", "", 8)
            _text(pdf, GRAY)
            pdf.multi_cell(col_str_w - 10, 4.2, _s(s))

    # ── Pro Reference ──────────────────────────────────────────────────────────
    if ref.get("player"):
        rx  = 14 + col_str_w + 8
        rw  = W - 14 - rx
        ry  = y - (len(strengths[:3]) * 9)  # align with strengths top
        ry  = max(ry, y - 40)

        _bg_rect(pdf, rx, ry, rw, 52, CARD)
        pdf.set_xy(rx + 4, ry + 4)
        pdf.set_font("Helvetica", "B", 7)
        _text(pdf, ACCENT)
        pdf.cell(rw - 8, 4, "STUDY THIS PROFESSIONAL", ln=True)

        pdf.set_xy(rx + 4, ry + 10)
        pdf.set_font("Helvetica", "B", 13)
        _text(pdf, WHITE)
        pdf.cell(rw - 8, 7, _s(ref.get("player", "")), ln=True)

        pdf.set_xy(rx + 4, ry + 18)
        pdf.set_font("Helvetica", "B", 8)
        _text(pdf, ACCENT)
        pdf.cell(rw - 8, 5, _s(ref.get("team", "")), ln=True)

        pdf.set_xy(rx + 4, ry + 25)
        pdf.set_font("Helvetica", "", 7.5)
        _text(pdf, GRAY)
        pdf.multi_cell(rw - 8, 4.2, _s(ref.get("note", ""))[:220])

        if ref.get("youtube_query"):
            pdf.set_xy(rx + 4, ry + 44)
            pdf.set_font("Helvetica", "B", 6.5)
            _text(pdf, DIM)
            pdf.cell(rw - 8, 4, f"SEARCH: {_s(ref['youtube_query'])[:50]}", ln=False)

    # ── Footer ─────────────────────────────────────────────────────────────────
    _fill(pdf, ACCENT)
    pdf.rect(0, H - 7, W, 7, style="F")
    pdf.set_xy(14, H - 5.5)
    pdf.set_font("Helvetica", "B", 7)
    _text(pdf, BLACK)
    pdf.cell(100, 5, "TACTIFY - AI SOCCER COACHING", ln=False)
    pdf.set_xy(110, H - 5.5)
    pdf.set_font("Helvetica", "", 7)
    pdf.cell(86, 5, "Powered by Claude AI  -  tactify.ai", align="R", ln=False)

    return bytes(pdf.output())
