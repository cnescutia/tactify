"""
Tactify — Analysis engine.

Claude Vision  → structured JSON (scores, annotations, insights, drills)
Pillow         → annotated still images
OpenCV + MediaPipe → pose-tracked annotated video with callout boxes
"""

import base64
import io
import json
import math
import os
import re
import tempfile
from typing import Callable

import anthropic
from knowledge_base import get_relevant_knowledge

# ── MediaPipe landmark index map ───────────────────────────────────────────────
# Indices are stable across MediaPipe versions (no import needed at module level)
_REGION_LANDMARKS = {
    "head":        [0, 7, 8],          # nose, left/right ear
    "upper_body":  [11, 12],           # shoulders
    "torso":       [11, 12, 23, 24],   # shoulders + hips
    "left_arm":    [13, 15],           # left elbow + wrist
    "right_arm":   [14, 16],           # right elbow + wrist
    "hips":        [23, 24],           # hips
    "left_leg":    [25],               # left knee
    "right_leg":   [26],               # right knee
    "feet":        [27, 28],           # ankles
    "left_foot":   [27],               # left ankle
    "right_foot":  [28],               # right ankle
    "body":        [23, 24],           # hips (general body)
}

# Static fallback positions (fraction of frame)
_REGION_FALLBACK = {
    "head": (0.50, 0.08), "upper_body": (0.50, 0.24), "torso": (0.50, 0.38),
    "left_arm": (0.26, 0.30), "right_arm": (0.74, 0.30),
    "hips": (0.50, 0.53), "left_leg": (0.37, 0.68), "right_leg": (0.63, 0.68),
    "feet": (0.50, 0.87), "left_foot": (0.37, 0.89), "right_foot": (0.63, 0.89),
    "body": (0.50, 0.50),
}

# BGR colors (OpenCV uses BGR)
_SEV_BGR = {
    "strength": (105, 255, 135),   # neon green
    "warning":  (30,  165, 255),   # amber
    "error":    (60,   60, 235),   # red
}

# RGB colors (Pillow)
_SEV_RGB = {
    "strength": (16, 185, 129),
    "warning":  (245, 158, 11),
    "error":    (239, 68, 68),
}


# ── Claude prompt ─────────────────────────────────────────────────────────────

ANALYSIS_PROMPT = """You are an elite professional soccer coach and technical analyst.
20+ years at the highest levels — European clubs, MLS, national teams.
You are reviewing footage to give a player actionable, specific feedback they can act on TODAY.

CONTEXT:
  Position  : {position}
  Situation : {play_type}
  Age Group : {age_group}
  Notes     : {notes}

COACHING KNOWLEDGE BASE:
{knowledge}

Study every image/frame carefully. Return ONLY a valid JSON object — no markdown, no extra text.
Images are numbered 1 through {num_frames} in the order provided.

{{
  "summary": "One powerful, specific sentence about this player's performance",

  "scores": {{
    "technique":         <integer 1-10>,
    "body_position":     <integer 1-10>,
    "spatial_awareness": <integer 1-10>,
    "decision_making":   <integer 1-10>,
    "effort":            <integer 1-10>
  }},

  "annotations": [
    {{
      "number":   1,
      "label":    "2-4 word label shown on video",
      "note":     "One specific coaching observation from the footage",
      "region":   "<head|upper_body|left_arm|right_arm|torso|hips|left_leg|right_leg|left_foot|right_foot|feet|body>",
      "severity": "<strength|warning|error>"
    }}
  ],

  "priority_fix": {{
    "title":      "Short title of the #1 thing to fix (5-7 words)",
    "what":       "What the player is doing wrong (1 sentence, specific)",
    "why":        "How this mistake costs them in a real game (1 sentence)",
    "cue":        "The single coaching cue they must remember — short, memorable, under 8 words",
    "drill": {{
      "name":          "Drill name",
      "duration":      "X min",
      "setup":         "How to set up and run the drill (2-3 sentences, specific: cones, distances, reps)",
      "focus":         "What to concentrate on during the drill (1 sentence)",
      "know_its_working": "How the player knows the drill is making a difference (1 sentence)"
    }}
  }},

  "fix_cards": [
    {{
      "mistake":       "What is wrong (short, direct)",
      "why_it_matters":"Real game consequence — what this costs them on the pitch (1 sentence)",
      "correction":    "Exactly what to do differently — be specific (1-2 sentences)",
      "cue":           "Short coaching cue (under 8 words)",
      "drill": {{
        "name":             "Drill name",
        "duration":         "X min",
        "setup":            "Setup and execution (2 sentences)",
        "know_its_working": "How they know it's improving (1 sentence)"
      }}
    }}
  ],

  "best_moment": {{
    "frame":       <integer 1-{num_frames}, which image shows the best technique>,
    "description": "What the player is doing well in this specific moment (1-2 sentences)"
  }},

  "worst_moment": {{
    "frame":       <integer 1-{num_frames}, which image shows the biggest mistake>,
    "what":        "What the mistake is (1 sentence)",
    "cause":       "What body mechanics cause it (1 sentence)",
    "effect":      "What happens in the game as a result (1 sentence)"
  }},

  "strengths":    ["...", "...", "..."],

  "pro_reference": {{
    "player":        "Full name",
    "team":          "Club or national team",
    "note":          "Two sentences on why this player is the benchmark for this situation.",
    "youtube_query": "A YouTube search query that will find a short clip of this player demonstrating the exact technique the player needs to improve. Be specific: include player name, technique name, and 'tutorial' or 'analysis'. Example: 'Luka Modric open body shape receiving tutorial'"
  }}
}}

3–5 annotations. 2–3 fix cards. Score 10 = professional level.
Fix cards must be tied to specific mistakes visible in the footage — no generic advice.
Drills must be specific: include distances, reps, or setup details a player can replicate alone.
"""


# ── Utilities ─────────────────────────────────────────────────────────────────

def _b64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("utf-8")


def _parse_json(text: str) -> dict | None:
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return None


def _extract_frames(video_bytes: bytes, num_frames: int = 4) -> list[bytes]:
    try:
        import cv2
    except ImportError:
        return []
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        path = tmp.name
    try:
        cap   = cv2.VideoCapture(path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total == 0:
            return []
        frames = []
        for i in range(num_frames):
            idx = int(total * (i + 1) / (num_frames + 1))
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                _, buf = cv2.imencode(".jpg", frame)
                frames.append(buf.tobytes())
        cap.release()
        return frames
    finally:
        os.unlink(path)


# ── Still image annotation (Pillow) ───────────────────────────────────────────

def annotate_image(image_bytes: bytes, annotations: list) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)
    r     = max(20, min(w, h) // 26)
    fsize = max(14, r - 4)

    font = None
    for path in ["/System/Library/Fonts/Helvetica.ttc",
                 "/System/Library/Fonts/Arial.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        try:
            font = ImageFont.truetype(path, fsize)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    for ann in annotations[:6]:
        region = ann.get("region", "body").lower()
        sev    = ann.get("severity", "warning")
        num    = ann.get("number", 1)
        frac   = _REGION_FALLBACK.get(region, (0.5, 0.5))
        px, py = int(frac[0] * w), int(frac[1] * h)
        rgb    = _SEV_RGB.get(sev, _SEV_RGB["warning"])

        for gr, ga in [(r + 12, 35), (r + 6, 70)]:
            tmp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(tmp).ellipse([px-gr, py-gr, px+gr, py+gr], fill=(*rgb, ga))
            layer = Image.alpha_composite(layer, tmp)
            draw  = ImageDraw.Draw(layer)

        draw.ellipse([px-r, py-r, px+r, py+r], fill=(*rgb, 230), outline=(255, 255, 255, 220), width=2)
        draw.text((px, py), str(num), fill=(255, 255, 255, 255), font=font, anchor="mm")

    result = Image.alpha_composite(img, layer).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="JPEG", quality=93)
    return buf.getvalue()


# ── OpenCV drawing helpers ────────────────────────────────────────────────────

def _dashed_line(frame, pt1, pt2, color, dash=10, gap=6, thickness=1):
    """Draw a dashed line between two points."""
    dx, dy = pt2[0] - pt1[0], pt2[1] - pt1[1]
    dist   = math.sqrt(dx * dx + dy * dy) or 1.0
    ux, uy = dx / dist, dy / dist
    pos, drawing = 0.0, True
    while pos < dist:
        end = min(pos + (dash if drawing else gap), dist)
        if drawing:
            import cv2
            x1 = int(pt1[0] + ux * pos);  y1 = int(pt1[1] + uy * pos)
            x2 = int(pt1[0] + ux * end);  y2 = int(pt1[1] + uy * end)
            cv2.line(frame, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)
        pos += dash if drawing else gap
        drawing = not drawing


def _get_landmark_pos(landmarks: list, region: str, w: int, h: int):
    """
    Return (px, py) from a MediaPipe Tasks landmark list for a given region, or None.
    landmarks = result.pose_landmarks[0]  (list of NormalizedLandmark)
    """
    indices = _REGION_LANDMARKS.get(region, [23, 24])
    pts = []
    for idx in indices:
        if idx >= len(landmarks):
            continue
        lm = landmarks[idx]
        vis = getattr(lm, "visibility", 1.0) or 0.0
        if vis > 0.35:
            pts.append((lm.x * w, lm.y * h))
    if not pts:
        return None
    return (int(sum(p[0] for p in pts) / len(pts)),
            int(sum(p[1] for p in pts) / len(pts)))


def _draw_callout(frame, ann: dict, body_pos: tuple, frame_idx: int, w: int, h: int):
    """
    Draw one pose-tracked callout annotation:
      • Pulsing dot at the actual body part position
      • Dashed line extending outward from the player
      • Callout box with numbered badge + label text
    """
    import cv2

    px, py = body_pos
    sev    = ann.get("severity", "warning")
    num    = ann.get("number", 1)
    label  = ann.get("label", "")[:20]
    bgr    = _SEV_BGR.get(sev, _SEV_BGR["warning"])
    pulse  = 0.60 + 0.40 * abs(math.sin(frame_idx * 0.06))

    # ── Dot at body part ──────────────────────────────────────────────────────
    r_dot = max(7, min(w, h) // 80)

    overlay = frame.copy()
    cv2.circle(overlay, (px, py), r_dot + 10, bgr, -1)
    cv2.addWeighted(overlay, 0.22 * pulse, frame, 1 - 0.22 * pulse, 0, frame)

    cv2.circle(frame, (px, py), r_dot, bgr, -1, cv2.LINE_AA)
    cv2.circle(frame, (px, py), r_dot, (255, 255, 255), 1, cv2.LINE_AA)

    # ── Line outward from player center ───────────────────────────────────────
    # Compute player center from hip region (rough)
    cx, cy  = w / 2, h / 2
    dx, dy  = (px - cx) or 1, (py - cy) or 1
    dist    = math.sqrt(dx * dx + dy * dy)
    ux, uy  = dx / dist, dy / dist
    line_len = max(70, min(w, h) // 6)

    ex = int(px + ux * line_len)
    ey = int(py + uy * line_len)
    ex = max(130, min(w - 130, ex))
    ey = max(22,  min(h - 22,  ey))

    _dashed_line(frame, (px, py), (ex, ey), bgr, thickness=1)

    # ── Callout box ───────────────────────────────────────────────────────────
    font   = cv2.FONT_HERSHEY_DUPLEX
    fs_lbl = max(0.30, min(w, h) / 1800)
    badge_r = max(9, min(w, h) // 70)
    pad     = 6

    (lw, lh), _ = cv2.getTextSize(label, font, fs_lbl, 1)
    box_w = badge_r * 2 + pad * 3 + lw
    box_h = max(badge_r * 2 + 4, lh + pad * 2)

    # Place box on the same side the line points to
    if ex >= w // 2:
        bx1 = ex
    else:
        bx1 = ex - box_w
    by1 = ey - box_h // 2
    bx2, by2 = bx1 + box_w, by1 + box_h

    # Clamp to frame
    if bx1 < 4:           shift = 4 - bx1;        bx1 += shift; bx2 += shift
    if bx2 > w - 4:       shift = bx2 - (w - 4);  bx1 -= shift; bx2 -= shift
    if by1 < 4:           shift = 4 - by1;         by1 += shift; by2 += shift
    if by2 > h - 4:       shift = by2 - (h - 4);   by1 -= shift; by2 -= shift

    # Box fill
    overlay = frame.copy()
    cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (6, 6, 6), -1)
    cv2.addWeighted(overlay, 0.88, frame, 0.12, 0, frame)
    cv2.rectangle(frame, (bx1, by1), (bx2, by2), bgr, 1, cv2.LINE_AA)

    # Numbered badge
    bcx = bx1 + badge_r + 4
    bcy = (by1 + by2) // 2
    cv2.circle(frame, (bcx, bcy), badge_r, bgr, -1, cv2.LINE_AA)
    fs_num = badge_r / 22.0
    (nw, nh), _ = cv2.getTextSize(str(num), font, fs_num, 1)
    cv2.putText(frame, str(num), (bcx - nw // 2, bcy + nh // 2),
                font, fs_num, (5, 5, 5), 1, cv2.LINE_AA)

    # Label
    ty = (by1 + by2) // 2 + lh // 2
    cv2.putText(frame, label, (bx1 + badge_r * 2 + pad * 2, ty),
                font, fs_lbl, (215, 215, 215), 1, cv2.LINE_AA)


def _draw_score_panel(frame, scores: dict, w: int, h: int):
    import cv2
    cats      = [("TECH", "technique"), ("POS", "body_position"), ("EFF", "effort")]
    panel_w   = max(180, min(w // 5, 240))
    row_h     = max(26, h // 28)
    panel_h   = 28 + len(cats) * row_h + 14
    margin    = 16
    x1, y1   = w - panel_w - margin, h - panel_h - margin
    x2, y2   = w - margin, h - margin

    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (5, 5, 5), -1)
    cv2.addWeighted(overlay, 0.80, frame, 0.20, 0, frame)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (28, 28, 28), 1)

    cv2.putText(frame, "TACTIFY", (x1 + 10, y1 + 18),
                cv2.FONT_HERSHEY_DUPLEX, 0.40, (0, 255, 135), 1, cv2.LINE_AA)

    for i, (lbl, key) in enumerate(cats):
        val = scores.get(key, 5)
        y   = y1 + 30 + i * row_h

        cv2.putText(frame, lbl, (x1 + 10, y + 14),
                    cv2.FONT_HERSHEY_DUPLEX, 0.34, (120, 120, 120), 1, cv2.LINE_AA)

        bx1b, bx2b = x1 + 52, x2 - 32
        by1b, by2b = y + 5, y + 11
        cv2.rectangle(frame, (bx1b, by1b), (bx2b, by2b), (28, 28, 28), -1)

        fill_w = int((bx2b - bx1b) * val / 10)
        c = _SEV_BGR["strength"] if val >= 8 else _SEV_BGR["warning"] if val >= 6 else _SEV_BGR["error"]
        cv2.rectangle(frame, (bx1b, by1b), (bx1b + fill_w, by2b), c, -1)

        cv2.putText(frame, str(val), (bx2b + 4, y + 14),
                    cv2.FONT_HERSHEY_DUPLEX, 0.36, (200, 200, 200), 1, cv2.LINE_AA)


# ── Pose-tracked video annotation ─────────────────────────────────────────────

def create_annotated_video(
    video_bytes: bytes,
    annotations: list,
    scores: dict,
    progress_callback: Callable | None = None,
) -> bytes | None:
    """
    Process every frame of the video:
    - MediaPipe Tasks PoseLandmarker detects actual body keypoints each frame
    - Callout boxes + dashed lines are drawn at the tracked positions
    - Annotations follow the player as they move
    Falls back to static positions if pose is not detected.
    """
    try:
        import cv2
        import mediapipe as mp
        from mediapipe.tasks.python import vision as mp_vision
    except ImportError:
        return None

    # Model must be alongside this file in models/
    model_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "models", "pose_landmarker_lite.task"
    )
    if not os.path.exists(model_path):
        print(f"Pose model not found: {model_path}")
        return None

    BaseOptions          = mp.tasks.BaseOptions
    PoseLandmarker       = mp_vision.PoseLandmarker
    PoseLandmarkerOptions = mp_vision.PoseLandmarkerOptions
    RunningMode          = mp_vision.RunningMode

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_in:
        tmp_in.write(video_bytes)
        in_path = tmp_in.name

    out_path = in_path + "_annotated.mp4"

    try:
        cap   = cv2.VideoCapture(in_path)
        fps   = cap.get(cv2.CAP_PROP_FPS) or 30.0
        w     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if w == 0 or h == 0 or total == 0:
            cap.release()
            return None

        for fourcc_str in ("avc1", "mp4v"):
            fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
            out    = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
            if out.isOpened():
                break

        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=RunningMode.VIDEO,
            min_pose_detection_confidence=0.4,
            min_pose_presence_confidence=0.4,
            min_tracking_confidence=0.4,
            num_poses=1,
        )

        frame_idx      = 0
        last_landmarks = None  # cache last good detection

        with PoseLandmarker.create_from_options(options) as landmarker:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                ts_ms    = int(frame_idx * 1000 / fps)

                result = landmarker.detect_for_video(mp_image, ts_ms)

                # result.pose_landmarks is a list of persons; take person 0
                if result.pose_landmarks:
                    last_landmarks = result.pose_landmarks[0]

                for ann in annotations[:6]:
                    region   = ann.get("region", "body").lower()
                    body_pos = None

                    if last_landmarks:
                        body_pos = _get_landmark_pos(last_landmarks, region, w, h)

                    if body_pos is None:
                        frac     = _REGION_FALLBACK.get(region, (0.5, 0.5))
                        body_pos = (int(frac[0] * w), int(frac[1] * h))

                    _draw_callout(frame, ann, body_pos, frame_idx, w, h)

                _draw_score_panel(frame, scores, w, h)
                out.write(frame)
                frame_idx += 1

                if progress_callback and frame_idx % 30 == 0:
                    pct = frame_idx / max(total, 1)
                    progress_callback(pct, f"Processing frame {frame_idx} / {total}")

        cap.release()
        out.release()

        if progress_callback:
            progress_callback(1.0, "Done")

        with open(out_path, "rb") as f:
            return f.read()

    except Exception as e:
        import traceback
        print(f"Video annotation error: {e}")
        traceback.print_exc()
        return None
    finally:
        for p in (in_path, out_path):
            try:
                os.unlink(p)
            except Exception:
                pass


# ── Main analysis (Claude Vision) ─────────────────────────────────────────────

def analyze_media(
    file_bytes: bytes,
    file_type: str,
    position: str,
    play_type: str,
    age_group: str,
    additional_notes: str = "",
) -> dict:
    """
    Send key frames to Claude, return structured JSON + annotated key frames.
    Does NOT build the annotated video — that's done separately so app.py can
    show a real-time progress bar.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"success": False, "error": "ANTHROPIC_API_KEY not set.",
                "data": None, "annotated_image": None, "key_frames": [], "frames_analyzed": 0}

    client    = anthropic.Anthropic(api_key=api_key)
    knowledge = get_relevant_knowledge(position, play_type)

    is_video   = file_type in ("video/mp4", "video/quicktime", "video/x-msvideo")
    media_type = "image/jpeg"

    if is_video:
        image_list = _extract_frames(file_bytes, 4)
        if not image_list:
            return {"success": False, "error": "Could not extract frames from video.",
                    "data": None, "annotated_image": None, "key_frames": [], "frames_analyzed": 0}
    else:
        image_list = [file_bytes]
        media_type = file_type.replace("image/jpg", "image/jpeg")

    num_frames = len(image_list)
    prompt    = ANALYSIS_PROMPT.format(
        position=position, play_type=play_type,
        age_group=age_group, notes=additional_notes or "None",
        knowledge=knowledge, num_frames=num_frames,
    )

    content = [
        {"type": "image",
         "source": {"type": "base64", "media_type": media_type, "data": _b64(fb)}}
        for fb in image_list
    ]
    content.append({"type": "text", "text": prompt})

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2800,
            messages=[{"role": "user", "content": content}],
        )
        data = _parse_json(response.content[0].text)
        if data is None:
            return {"success": False, "error": "Could not parse AI response. Please try again.",
                    "data": None, "annotated_image": None, "key_frames": [], "frames_analyzed": len(image_list)}

        anns = data.get("annotations", [])

        annotated_image = None
        try:
            annotated_image = annotate_image(image_list[0], anns)
        except Exception:
            pass

        key_frames = []
        for fb in image_list:
            try:
                key_frames.append(annotate_image(fb, anns))
            except Exception:
                key_frames.append(fb)

        return {
            "success": True, "error": "",
            "data": data,
            "annotated_image": annotated_image,
            "key_frames": key_frames,
            "frames_analyzed": len(image_list),
        }

    except anthropic.APIError as e:
        return {"success": False, "error": f"API error: {e}",
                "data": None, "annotated_image": None, "key_frames": [], "frames_analyzed": 0}


# ── Coaching Audio Narration ───────────────────────────────────────────────────

def generate_coaching_audio(data: dict, position: str) -> bytes | None:
    """
    Convert analysis data into a natural coaching narration and return MP3 bytes.
    Returns None if gTTS is unavailable or narration fails.
    """
    try:
        from gtts import gTTS
    except ImportError:
        return None

    pf        = data.get("priority_fix", {})
    best      = data.get("best_moment", {})
    worst     = data.get("worst_moment", {})
    fix_cards = data.get("fix_cards", [])
    strengths = data.get("strengths", [])
    ref       = data.get("pro_reference", {})
    summary   = data.get("summary", "")

    lines = []

    # Opening
    lines.append(f"Alright, let's go through your session.")
    if summary:
        lines.append(summary)

    # Priority fix
    if pf.get("title"):
        lines.append(f"Your number one priority right now: {pf['title']}.")
        if pf.get("what"):
            lines.append(pf["what"])
        if pf.get("why"):
            lines.append(f"Here's why this matters. {pf['why']}")
        if pf.get("cue"):
            lines.append(f"The cue I want you to carry into every rep: {pf['cue']}.")

    # Best moment
    if best.get("description"):
        lines.append(f"Your best moment this session — {best['description']} That's the standard. Remember that feeling.")

    # Worst moment
    if worst.get("what"):
        lines.append(f"Now here's what cost you. {worst['what']}.")
        if worst.get("cause"):
            lines.append(f"Why does it happen? {worst['cause']}")
        if worst.get("effect"):
            lines.append(f"In a game, that means: {worst['effect']}")

    # Fix cards
    if fix_cards:
        lines.append(f"I've got {min(len(fix_cards), 3)} specific fixes for you.")
        for i, card in enumerate(fix_cards[:3], 1):
            mistake    = card.get("mistake", "")
            correction = card.get("correction", "")
            cue        = card.get("cue", "")
            if mistake:
                lines.append(f"Fix {i}: {mistake}.")
            if correction:
                lines.append(correction)
            if cue:
                lines.append(f"Cue: {cue}.")

    # Strengths
    if strengths:
        lines.append("Here's what you're doing well.")
        for s in strengths[:2]:
            lines.append(s)
        lines.append("Keep doing that.")

    # Pro reference
    if ref.get("player"):
        player = ref["player"]
        team   = ref.get("team", "")
        note   = ref.get("note", "")
        lines.append(f"Study {player}" + (f" from {team}" if team else "") + ".")
        if note:
            lines.append(note)

    # Closing
    lines.append("Now get to work. See you next session.")

    script = " ".join(lines)

    try:
        tts = gTTS(text=script, lang="en", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None


# ── Session Comparison (Before / After) ───────────────────────────────────────

_COMPARISON_PROMPT = """
You are comparing two soccer coaching analysis sessions for the same player.

BEFORE SESSION:
{before}

AFTER SESSION:
{after}

Return ONLY valid JSON (no markdown fences):
{{
  "headline": "one punchy sentence summarising the overall progress direction",
  "score_deltas": {{
    "technique": <integer: after score minus before score>,
    "body_position": <integer>,
    "spatial_awareness": <integer>,
    "decision_making": <integer>,
    "effort": <integer>
  }},
  "improvements": ["specific thing that measurably improved, with evidence"],
  "still_needs_work": ["things that have not changed enough yet"],
  "regression": ["anything that got worse, or empty list if none"],
  "next_session_focus": "the single highest-leverage thing to work on next session",
  "coach_note": "honest, encouraging 2-3 sentence message directly to the player"
}}
"""


def compare_sessions(before_data: dict, after_data: dict) -> dict | None:
    """
    Use Claude to compare two analysis sessions and return a progress report dict.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _COMPARISON_PROMPT.format(
        before=json.dumps(before_data, indent=2),
        after=json.dumps(after_data, indent=2),
    )
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_json(response.content[0].text)
    except Exception:
        return None


def generate_comparison_audio(comparison: dict) -> bytes | None:
    """Generate coaching narration for a before/after comparison report."""
    try:
        from gtts import gTTS
    except ImportError:
        return None

    lines = []

    headline = comparison.get("headline", "")
    if headline:
        lines.append(f"Alright, let's talk about your progress. {headline}")

    improvements = comparison.get("improvements", [])
    if improvements:
        lines.append("Here's what's improved.")
        for item in improvements[:3]:
            lines.append(item)

    still = comparison.get("still_needs_work", [])
    if still:
        lines.append("Here's what still needs more work.")
        for item in still[:2]:
            lines.append(item)

    regression = comparison.get("regression", [])
    if regression:
        lines.append("One thing to flag.")
        for item in regression[:1]:
            lines.append(item)

    next_focus = comparison.get("next_session_focus", "")
    if next_focus:
        lines.append(f"Next session, your one focus is: {next_focus}.")

    note = comparison.get("coach_note", "")
    if note:
        lines.append(note)

    lines.append("Keep building. The work is showing.")

    script = " ".join(lines)
    try:
        tts = gTTS(text=script, lang="en", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None


# ── Team Analysis ──────────────────────────────────────────────────────────────

_TEAM_PROMPT = """
You are a technical director reviewing individual coaching reports for {n} players on the same team.

PLAYER REPORTS:
{reports}

Identify systemic patterns — weaknesses or habits that appear across multiple players.
Return ONLY valid JSON (no markdown fences):
{{
  "team_headline": "One sharp sentence on the team's collective state right now.",
  "systemic_issues": [
    "A specific technical or tactical problem that appears in 2 or more players (be specific, reference what you see in the data)"
  ],
  "team_strengths": [
    "A collective strength visible across the squad"
  ],
  "weakest_category": "The one score category (technique/body_position/spatial_awareness/decision_making/effort) with the lowest team average",
  "recommended_team_drill": {{
    "name":             "Drill name",
    "duration":         "e.g. 15 min",
    "setup":            "What you need and how to set it up",
    "focus":            "What players are specifically working on",
    "know_its_working": "Observable sign that the team is executing correctly"
  }},
  "individual_notes": [
    {{
      "player":       "Player name as provided",
      "top_strength": "Their single biggest asset",
      "priority_fix": "Their single most urgent improvement"
    }}
  ]
}}

individual_notes must have exactly {n} entries, one per player in the same order as the input.
"""


def analyze_team_patterns(player_results: list[dict]) -> dict | None:
    """
    Given a list of dicts with keys 'name' and 'data' (analysis output),
    use Claude to identify systemic team patterns.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    reports_payload = []
    for pr in player_results:
        d = pr["data"]
        reports_payload.append({
            "player": pr["name"],
            "scores": d.get("scores", {}),
            "summary": d.get("summary", ""),
            "priority_fix": d.get("priority_fix", {}).get("title", ""),
            "fix_cards": [c.get("mistake", "") for c in d.get("fix_cards", [])],
            "strengths": d.get("strengths", [])[:2],
        })

    prompt = _TEAM_PROMPT.format(
        n=len(player_results),
        reports=json.dumps(reports_payload, indent=2),
    )

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1400,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_json(response.content[0].text)
    except Exception:
        return None
