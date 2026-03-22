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

import shutil

import anthropic
from dotenv import load_dotenv
from knowledge_base import get_relevant_knowledge

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=True)


def _ffmpeg_exe() -> str | None:
    """Return path to ffmpeg binary: system install first, then imageio-ffmpeg bundle."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None

def _downscale_video(video_bytes: bytes, max_height: int = 720) -> bytes:
    """Downscale video to max_height using ffmpeg. Returns original bytes on failure."""
    import subprocess, tempfile, os
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        return video_bytes
    try:
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as inp:
            inp.write(video_bytes)
            inp_path = inp.name
        out_path = inp_path.replace('.mp4', '_scaled.mp4')
        r = subprocess.run([
            ffmpeg, '-y', '-i', inp_path,
            '-vf', f'scale=-2:{max_height}',
            '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
            '-c:a', 'copy', out_path
        ], capture_output=True, timeout=60)
        if r.returncode == 0:
            with open(out_path, 'rb') as f:
                result = f.read()
            return result if len(result) > 1000 else video_bytes
        return video_bytes
    except Exception:
        return video_bytes
    finally:
        for p in [inp_path, out_path]:
            try: os.unlink(p)
            except: pass


def _locate_player_joints(frame_bytes: bytes) -> dict:
    """Fast dedicated Claude Haiku call to precisely locate player joints in ONE frame.
    Returns dict with 'joints' key mapping joint names to {x, y} fractions, or {} on failure."""
    try:
        import base64 as _base64, re as _re, json as _json
        client = anthropic.Anthropic()
        b64 = _base64.standard_b64encode(frame_bytes).decode()
        prompt = (
            "You are a precise pose estimation system. ONE task only: locate the soccer player's "
            "body joints in this image as (x,y) fractions of image width/height.\n\n"
            "RULES:\n"
            "- x=0.0 = left edge, x=1.0 = right edge\n"
            "- y=0.0 = top edge, y=1.0 = bottom edge\n"
            "- BE PRECISE. If the player stands left of centre, head x should be ~0.25, NOT 0.5.\n"
            "- If a joint is hidden or out of frame, use -1 for both x and y.\n"
            "- Focus on the PRIMARY player only. Ignore background players.\n\n"
            "Return ONLY valid JSON, no other text:\n"
            '{"player_found": true, "joints": {'
            '"head": {"x": 0.0, "y": 0.0}, '
            '"left_shoulder": {"x": 0.0, "y": 0.0}, "right_shoulder": {"x": 0.0, "y": 0.0}, '
            '"left_elbow": {"x": 0.0, "y": 0.0}, "right_elbow": {"x": 0.0, "y": 0.0}, '
            '"left_wrist": {"x": 0.0, "y": 0.0}, "right_wrist": {"x": 0.0, "y": 0.0}, '
            '"left_hip": {"x": 0.0, "y": 0.0}, "right_hip": {"x": 0.0, "y": 0.0}, '
            '"left_knee": {"x": 0.0, "y": 0.0}, "right_knee": {"x": 0.0, "y": 0.0}, '
            '"left_ankle": {"x": 0.0, "y": 0.0}, "right_ankle": {"x": 0.0, "y": 0.0}'
            '}}'
        )
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=400,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": prompt},
            ]}],
        )
        text = resp.content[0].text.strip()
        m = _re.search(r'\{.*\}', text, _re.DOTALL)
        if m:
            return _json.loads(m.group())
    except Exception:
        pass
    return {}


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

ANALYSIS_PROMPT = """You are a senior technical coach at a professional soccer club, with experience at top European and South American academies.
You see exactly what you see in the footage — no assumptions, no generic observations.
Every piece of feedback must be directly tied to something visible in these specific frames.

CONTEXT:
  Position  : {position}
  Situation : {play_type}
  Age Group : {age_group}
  Coach Notes: {notes}

COACHING KNOWLEDGE BASE:
{knowledge}

Study every frame with the eye of a scout preparing a dossier for the coaching staff.
Return ONLY a valid JSON object — no markdown, no commentary outside the JSON.
Frames are numbered 1–{num_frames} in the order provided.

LANGUAGE STANDARD:
- Use technical coaching vocabulary: "body shape", "scanning", "first touch direction",
  "weight of pass", "hip orientation", "center of gravity", "pressure timing", "press trigger"
- Be specific about which foot, which shoulder, which direction
- Name specific game situations: "counter-press", "third-man run", "switch of play", "overlapping run"
- Never write advice that could apply to any random player — tie it to what you literally see
- Scores: 10 = professional starter level, 7 = high-level youth, 5 = recreational adult, 3 = significant technical gaps

{{
  "summary": "One sharp, specific sentence that could open a real scouting report on this player",

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
      "label":    "3-5 word technical label (e.g. 'Closed hip — missed lane')",
      "note":     "One precise coaching observation referencing specific body mechanics visible in the frame",
      "region":   "<head|upper_body|left_arm|right_arm|torso|hips|left_leg|right_leg|left_foot|right_foot|feet|body>",
      "severity": "<strength|warning|error>",
      "frame":    <integer 1–{num_frames} — which frame BEST shows this issue>,
      "x_pct":    <float 0.0–1.0 — horizontal position of the annotated body part in that frame; 0=left edge, 1=right edge — look at where the body part ACTUALLY is>,
      "y_pct":    <float 0.0–1.0 — vertical position; 0=top edge, 1=bottom edge — look at the ACTUAL position>,
      "vector":   {{"dx": <float -1 to 1>, "dy": <float -1 to 1>}}
    }}
  ],

  "priority_fix": {{
    "title":      "The single most important technical fix (5-8 words)",
    "what":       "Exact description of the technical error visible in the footage — specific body part, specific action",
    "why":        "The direct game consequence of this error in a real professional match",
    "cue":        "One coaching cue the player repeats in their head — crisp, memorable, under 8 words",
    "drill": {{
      "name":          "Specific drill name",
      "duration":      "X min",
      "setup":         "Precise setup: cone distances, partner needed or solo, reps, surface. A player should be able to replicate this in 60 seconds of reading.",
      "focus":         "The one mechanical thing to concentrate on during the drill",
      "know_its_working": "Observable sign the player can self-check to confirm improvement"
    }}
  }},

  "fix_cards": [
    {{
      "mistake":        "Name of the technical error (short, direct — what a coach would write in a match report)",
      "why_it_matters": "Specific game cost — what does this error cause in a real match situation?",
      "correction":     "Precisely what the player must do differently — reference the body part and the timing",
      "cue":            "Short coaching cue under 8 words",
      "drill": {{
        "name":              "Drill name",
        "duration":          "X min",
        "setup":             "Specific setup with reps, distances, or partner instructions",
        "know_its_working":  "Self-check: how the player knows the correction is clicking"
      }}
    }}
  ],

  "best_moment": {{
    "frame":       <integer 1–{num_frames} — which frame shows the cleanest technique>,
    "description": "What specifically is correct here — body mechanics, decision, timing. Reference exactly what you see."
  }},

  "worst_moment": {{
    "frame":       <integer 1–{num_frames} — which frame shows the most costly error>,
    "what":        "The specific technical mistake — name it precisely",
    "cause":       "The mechanical root cause — what body position or timing error creates this",
    "effect":      "What this costs the player or team in that specific game moment"
  }},

  "strengths": [
    "3 specific technical strengths that are genuinely visible in this footage — not generic praise"
  ],

  "pro_reference": {{
    "player":        "Full name of an active or recently-retired professional",
    "team":          "Current or most recent club / national team",
    "note":          "Why this specific pro is the benchmark for this exact technical element the player needs to improve. Be precise about which skill and why.",
    "youtube_query": "Search query to find a clip of this pro demonstrating that exact technique. Include: player name + specific skill + 'analysis' or 'tutorial'. E.g.: 'Rodri ball retention under pressure analysis'"
  }},

  "skeleton": {{
    "frame": <integer 1–{num_frames} — the frame that shows the clearest full-body stance>,
    "joints": {{
      "head":           {{"x": <0-1>, "y": <0-1>}},
      "left_shoulder":  {{"x": <0-1>, "y": <0-1>}},
      "right_shoulder": {{"x": <0-1>, "y": <0-1>}},
      "left_elbow":     {{"x": <0-1>, "y": <0-1>}},
      "right_elbow":    {{"x": <0-1>, "y": <0-1>}},
      "left_wrist":     {{"x": <0-1>, "y": <0-1>}},
      "right_wrist":    {{"x": <0-1>, "y": <0-1>}},
      "left_hip":       {{"x": <0-1>, "y": <0-1>}},
      "right_hip":      {{"x": <0-1>, "y": <0-1>}},
      "left_knee":      {{"x": <0-1>, "y": <0-1>}},
      "right_knee":     {{"x": <0-1>, "y": <0-1>}},
      "left_ankle":     {{"x": <0-1>, "y": <0-1>}},
      "right_ankle":    {{"x": <0-1>, "y": <0-1>}}
    }},
    "key_angles": [
      {{
        "label":      "Short label, e.g. 'L Knee' or 'R Hip'",
        "a":          "<proximal joint name from the joints dict>",
        "b":          "<the measured joint — the vertex>",
        "c":          "<distal joint name>",
        "degrees":    <integer — estimated angle at this joint in degrees>,
        "assessment": "<good|warning|error>",
        "note":       "One sentence: why this angle matters for this specific action"
      }}
    ]
  }}
}}

REQUIREMENTS:
- 5–6 annotations spread across different body regions and different frames
- 2–3 fix cards, each a distinct technical issue
- Every note/correction must reference something literally visible in the footage
- Drills must be executable solo unless stated — include distances in meters or yards, rep counts
- No generic soccer advice. This is used by professional coaches and players worldwide.
- x_pct / y_pct PRECISION — this is critical for annotation placement. Think of each frame as a grid:
    Horizontal thirds: left-third x≈0.15, center x≈0.50, right-third x≈0.85
    Vertical quarters: head/sky y≈0.05–0.15, upper body y≈0.20–0.35, hips y≈0.45–0.55, knees y≈0.60–0.70, feet y≈0.80–0.92
    A player standing left-of-center has x_pct ~0.30; their planting foot at bottom of frame has y_pct ~0.88.
    Look at the ACTUAL pixel position of the specific body part. Do NOT default to 0.5/0.5. Do NOT use the same x/y for multiple annotations.
- vector field: Include ONLY when there is a clear directional correction or movement to show (body rotation, weight shift, pass direction, run path, hip opening). Use dx/dy as a normalized direction unit: positive x = right, negative x = left, positive y = downward, negative y = upward. Magnitude 0.15–0.55. Omit "vector" entirely for static technique issues (e.g. stiff ankle, wrong foot planted). Examples: hip needs to open left → {{"dx": -0.4, "dy": 0.1}}; player should step forward → {{"dx": 0.1, "dy": 0.35}}.
- skeleton: Pick the ONE frame that shows the clearest full-body pose. Map every visible joint to its ACTUAL pixel position as x/y fractions. If a joint is hidden or out of frame set both to -1. Include 2–4 key_angles at the joints most relevant to the coaching feedback (e.g. knee flexion on contact, hip angle on pass). assessment=good means the angle is optimal for the action; warning means improvable; error means a technical flaw.
"""


# ── Utilities ─────────────────────────────────────────────────────────────────

def _b64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("utf-8")

def _compress_frame(img_bytes: bytes, max_w: int = 800, max_h: int = 600, quality: int = 70) -> bytes:
    """Resize + JPEG-compress a frame so it stays under the API size limit."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        w, h = img.size
        # Always resize to ensure small payload
        scale = min(max_w / max(w, 1), max_h / max(h, 1), 1.0)
        new_w, new_h = int(w * scale), int(h * scale)
        if new_w != w or new_h != h:
            img = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        compressed = buf.getvalue()
        # If still > 1MB, compress harder
        if len(compressed) > 1_000_000:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=50, optimize=True)
            compressed = buf.getvalue()
        return compressed
    except Exception:
        return img_bytes  # fallback: return original if PIL fails



def _parse_json(text: str) -> dict | None:
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    text = re.sub(r"```\s*$", "", text).strip()

    # 1. Try clean parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Extract outermost {...} block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    # 3. Truncated response recovery — find the largest valid prefix
    # Walk backwards from end, trying to close any open braces/brackets
    raw = m.group() if m else text
    for end in range(len(raw), 0, -1):
        candidate = raw[:end]
        # Count open braces/brackets and try to close them
        opens = candidate.count("{") - candidate.count("}")
        opens_sq = candidate.count("[") - candidate.count("]")
        if opens < 0 or opens_sq < 0:
            continue
        closed = candidate + ("]" * opens_sq) + ("}" * opens)
        try:
            result = json.loads(closed)
            if isinstance(result, dict) and "scores" in result:
                print("[tactify] _parse_json: recovered truncated JSON")
                return result
        except json.JSONDecodeError:
            continue

    return None


def _extract_frames(video_bytes: bytes, num_frames: int = 4) -> list[bytes]:
    """
    Extract evenly-spaced frames without ffprobe.
    Multiple fallback strategies so something always works on cloud.
    """
    import subprocess

    try:
        import imageio_ffmpeg
    except ImportError:
        print("[tactify] imageio_ffmpeg not available")
        return []

    # Use a suffix that ffmpeg auto-detects; .mp4 is fine for most uploads
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        path = tmp.name

    try:
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"[tactify] ffmpeg binary: {ffmpeg_bin}")

        # ── Strategy 1: imageio_ffmpeg.read_frames() raw frame iteration ─────
        # Most reliable on cloud — uses the bundled binary internally
        try:
            from PIL import Image as _PILImage
            gen  = imageio_ffmpeg.read_frames(path)
            meta = next(gen)
            w, h = meta["size"]
            print(f"[tactify] meta: size={w}x{h} duration={meta.get('duration')}")

            # Cap to num_frames+1 raw frames max to avoid OOM on 4K video
            raw_frames: list[bytes] = []
            for raw in gen:
                raw_frames.append(raw)
                if len(raw_frames) >= num_frames + 1:
                    break
            gen.close()

            if raw_frames:
                n       = len(raw_frames)
                indices = [int(n * (i + 1) / (num_frames + 1)) for i in range(num_frames)]
                result  = []
                # Scale down to max 800x600 before saving to JPEG to save memory
                MAX_W, MAX_H = 800, 600
                scale = min(MAX_W / max(w, 1), MAX_H / max(h, 1), 1.0)
                out_w, out_h = max(int(w * scale), 1), max(int(h * scale), 1)
                for idx in indices:
                    frame_raw = raw_frames[min(idx, n - 1)]
                    img = _PILImage.frombytes("RGB", (w, h), frame_raw)
                    if scale < 1.0:
                        img = img.resize((out_w, out_h), _PILImage.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=72, optimize=True)
                    result.append(buf.getvalue())
                print(f"[tactify] strategy-1 extracted {len(result)} frames ({out_w}x{out_h})")
                return result
        except Exception as e:
            print(f"[tactify] strategy-1 failed: {e}")

        # ── Strategy 2: subprocess PNG pipe at timestamps ─────────────────────
        duration = 0.0
        try:
            gen      = imageio_ffmpeg.read_frames(path)
            meta     = next(gen)
            gen.close()
            duration = float(meta.get("duration") or 0)
        except Exception:
            pass

        timestamps = (
            [duration * (i + 1) / (num_frames + 1) for i in range(num_frames)]
            if duration > 0.5
            else [0.0] * num_frames
        )

        result = []
        for ts in timestamps:
            cmd = [ffmpeg_bin, "-y"]
            if ts > 0:
                cmd += ["-ss", f"{ts:.3f}"]
            # Scale down to max 800px wide before piping to avoid large PNGs
            cmd += ["-i", path, "-frames:v", "1",
                    "-vf", "scale='min(800,iw)':-2",
                    "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "5", "pipe:1"]
            r = subprocess.run(cmd, capture_output=True, timeout=30)
            if r.returncode == 0 and len(r.stdout) > 100:
                result.append(r.stdout)
            else:
                print(f"[tactify] strategy-2 ts={ts:.1f} rc={r.returncode} "
                      f"stderr={r.stderr[-200:].decode(errors='replace')}")

        if result:
            print(f"[tactify] strategy-2 extracted {len(result)} frames")
            return result

        # ── Strategy 3: first frame JPEG pipe ────────────────────────────────
        r = subprocess.run(
            [ffmpeg_bin, "-y", "-i", path,
             "-frames:v", "1", "-vf", "scale='min(800,iw)':-2",
             "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "5", "pipe:1"],
            capture_output=True, timeout=30,
        )
        if r.returncode == 0 and len(r.stdout) > 100:
            print("[tactify] strategy-3 (mjpeg) succeeded")
            return [r.stdout] * num_frames
        print(f"[tactify] strategy-3 failed rc={r.returncode} "
              f"stderr={r.stderr[-200:].decode(errors='replace')}")

        return []

    except Exception as e:
        print(f"[tactify] _extract_frames outer exception: {e}")
        return []
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass




# ── Shared annotation rendering (PIL) ─────────────────────────────────────────

def _load_fonts(fsize_num: int, fsize_label: int):
    from PIL import ImageFont
    for path in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        try:
            return ImageFont.truetype(path, fsize_num), ImageFont.truetype(path, fsize_label)
        except Exception:
            continue
    d = ImageFont.load_default()
    return d, d


# Skeleton bone connections (joint_a, joint_b)
_BONES = [
    ("head",          "left_shoulder"),
    ("head",          "right_shoulder"),
    ("left_shoulder", "right_shoulder"),   # collar
    ("left_shoulder", "left_elbow"),
    ("left_elbow",    "left_wrist"),
    ("right_shoulder","right_elbow"),
    ("right_elbow",   "right_wrist"),
    ("left_shoulder", "left_hip"),         # torso left
    ("right_shoulder","right_hip"),        # torso right
    ("left_hip",      "right_hip"),        # pelvis
    ("left_hip",      "left_knee"),
    ("left_knee",     "left_ankle"),
    ("right_hip",     "right_knee"),
    ("right_knee",    "right_ankle"),
]

_ANGLE_COLOR = {
    "good":    (16,  185, 129),   # neon green
    "warning": (245, 158,  11),   # amber
    "error":   (239,  68,  68),   # red
}


def _draw_skeleton_layer(w: int, h: int, skeleton: dict) -> "Image.Image":
    """
    Render a biomechanics skeleton overlay: bone lines, joint dots, and
    angle arcs with degree labels onto a transparent RGBA canvas.
    """
    from PIL import Image, ImageDraw
    import math as _math

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    joints_raw = skeleton.get("joints", {})

    # Convert normalised coords → pixel coords, skip hidden joints (x/y == -1)
    joints: dict = {}
    for name, jv in joints_raw.items():
        if not isinstance(jv, dict):
            continue
        xn, yn = float(jv.get("x", -1)), float(jv.get("y", -1))
        if xn < 0 or yn < 0 or xn > 1 or yn > 1:
            continue
        joints[name] = (int(xn * w), int(yn * h))

    if not joints:
        return layer

    bone_w = max(2, w // 240)   # scale line width to image size

    # ── Bone lines ────────────────────────────────────────────────────────────
    for ja, jb in _BONES:
        if ja in joints and jb in joints:
            draw.line([joints[ja], joints[jb]], fill=(220, 220, 220, 130), width=bone_w)

    # ── Joint dots ────────────────────────────────────────────────────────────
    jr = max(4, w // 130)
    for name, (px, py) in joints.items():
        draw.ellipse([px - jr, py - jr, px + jr, py + jr],
                     fill=(255, 255, 255, 200), outline=(0, 0, 0, 180), width=1)

    # ── Angle arcs + degree labels ────────────────────────────────────────────
    font_ang, _ = _load_fonts(max(11, w // 55), max(9, w // 70))

    for ang in skeleton.get("key_angles", []):
        ja, jb, jc = ang.get("a"), ang.get("b"), ang.get("c")
        if not (ja in joints and jb in joints and jc in joints):
            continue

        ax, ay = joints[ja]
        bx, by = joints[jb]
        cx, cy = joints[jc]

        # Vectors from vertex B
        vax, vay = ax - bx, ay - by
        vcx, vcy = cx - bx, cy - by
        mag_a = _math.sqrt(vax**2 + vay**2) or 1
        mag_c = _math.sqrt(vcx**2 + vcy**2) or 1

        # Angle arc: use fractions of the shorter bone for arc radius
        arc_r = max(18, int(min(mag_a, mag_c) * 0.35))
        arc_r = min(arc_r, w // 12)

        # Start/end angles for PIL arc (degrees from east/3 o'clock, clockwise)
        angle_a = _math.degrees(_math.atan2(vay, vax))
        angle_c = _math.degrees(_math.atan2(vcy, vcx))

        # Always draw the shorter arc
        diff = ((angle_c - angle_a + 180) % 360) - 180
        start_deg = angle_a
        end_deg   = angle_a + diff

        c_rgb = _ANGLE_COLOR.get(ang.get("assessment", "warning"), _ANGLE_COLOR["warning"])

        bbox = [bx - arc_r, by - arc_r, bx + arc_r, by + arc_r]
        draw.arc(bbox, start=start_deg, end=end_deg, fill=(*c_rgb, 210), width=max(2, bone_w + 1))

        # Degree label positioned along the bisector of the arc
        mid_angle_rad = _math.radians((start_deg + end_deg) / 2)
        lx = int(bx + (arc_r + max(14, w // 55)) * _math.cos(mid_angle_rad))
        ly = int(by + (arc_r + max(14, w // 55)) * _math.sin(mid_angle_rad))
        lx = max(4, min(w - 4, lx))
        ly = max(4, min(h - 4, ly))

        deg_text = f"{int(ang.get('degrees', 0))}°"
        lbl_text = ang.get("label", "")

        # Tiny dark pill background
        try:
            bbox_t = draw.textbbox((0, 0), deg_text, font=font_ang)
            tw, th = bbox_t[2] - bbox_t[0], bbox_t[3] - bbox_t[1]
        except AttributeError:
            tw, th = len(deg_text) * 7, 12
        pad = 3
        pill = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(pill).rectangle(
            [lx - pad, ly - pad, lx + tw + pad, ly + th + pad],
            fill=(*c_rgb, 200),
        )
        layer = Image.alpha_composite(layer, pill)
        draw  = ImageDraw.Draw(layer)
        draw.text((lx, ly), deg_text, fill=(10, 10, 10, 255), font=font_ang)

        # Tiny label underneath degree (optional — only if it fits)
        if lbl_text and w > 400:
            _, font_lbl2 = _load_fonts(max(11, w // 55), max(9, w // 75))
            draw.text((lx, ly + th + 2), lbl_text,
                      fill=(*c_rgb, 180), font=font_lbl2)

    return layer


def _build_overlay(w: int, h: int, annotations: list, scores: dict,
                   skeleton: dict | None = None) -> "Image.Image":
    """
    Render skeleton bones/angles (bottom layer), colored dots, directional arrows,
    callout labels, and score bars onto a transparent RGBA canvas.
    """
    from PIL import Image, ImageDraw

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # Skeleton layer goes under everything else
    if skeleton and isinstance(skeleton, dict) and skeleton.get("joints"):
        try:
            skel_layer = _draw_skeleton_layer(w, h, skeleton)
            layer = Image.alpha_composite(layer, skel_layer)
        except Exception:
            pass

    draw  = ImageDraw.Draw(layer)

    r           = max(14, min(w, h) // 30)
    fsize_num   = max(12, r - 4)
    fsize_label = max(10, r - 6)
    font_num, font_lbl = _load_fonts(fsize_num, fsize_label)

    for ann in annotations[:6]:
        region = ann.get("region", "body").lower()
        sev    = ann.get("severity", "warning")
        num    = ann.get("number", 1)
        lbl    = ann.get("label", "")[:28]
        rgb    = _SEV_RGB.get(sev, _SEV_RGB["warning"])

        # Position priority: 1) Claude x_pct/y_pct  2) skeleton joints  3) fallback
        _region_to_joints = {
            "head": ["head"], "upper_body": ["left_shoulder", "right_shoulder"],
            "left_arm": ["left_elbow", "left_wrist"], "right_arm": ["right_elbow", "right_wrist"],
            "torso": ["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
            "hips": ["left_hip", "right_hip"], "left_leg": ["left_knee"],
            "right_leg": ["right_knee"], "left_foot": ["left_ankle"],
            "right_foot": ["right_ankle"], "feet": ["left_ankle", "right_ankle"],
            "body": ["left_hip", "right_hip"],
        }
        if ann.get("x_pct") is not None and ann.get("y_pct") is not None:
            xv, yv = float(ann["x_pct"]), float(ann["y_pct"])
            if 0.02 < xv < 0.98 and 0.02 < yv < 0.98:   # reject edge defaults
                px, py = int(xv * w), int(yv * h)
            else:
                px, py = None, None
        else:
            px, py = None, None
        if px is None:
            # Try skeleton joints for this region
            skel = skeleton if skeleton else {}
            joint_names = _region_to_joints.get(region, [])
            jdata = skel.get("joints", {})
            _pts = [(float(jdata[j]["x"]), float(jdata[j]["y"])) for j in joint_names
                    if j in jdata and float(jdata[j].get("x",-1)) > 0 and float(jdata[j].get("y",-1)) > 0]
            if _pts:
                px = int(sum(p[0] for p in _pts) / len(_pts) * w)
                py = int(sum(p[1] for p in _pts) / len(_pts) * h)
            else:
                fx, fy = _REGION_FALLBACK.get(region, (0.5, 0.5))
                px, py = int(fx * w), int(fy * h)
        px = max(r + 4, min(w - r - 4, px))
        py = max(r + 4, min(h - r - 4, py))

        # ── Vector arrow ──────────────────────────────────────────────────────
        vec = ann.get("vector")
        if vec and isinstance(vec, dict):
            vdx = float(vec.get("dx", 0))
            vdy = float(vec.get("dy", 0))
            mag = math.sqrt(vdx * vdx + vdy * vdy)
            if mag > 0.05:
                arrow_len = max(50, min(w, h) // 5)
                ex = max(4, min(w - 4, int(px + (vdx / mag) * arrow_len)))
                ey = max(4, min(h - 4, int(py + (vdy / mag) * arrow_len)))
                # Thick shaft
                draw.line([(px, py), (ex, ey)], fill=(*rgb, 220), width=4)
                # Arrowhead
                adx, ady = ex - px, ey - py
                dist = math.sqrt(adx * adx + ady * ady) or 1
                ux, uy  = adx / dist, ady / dist
                head    = max(14, arrow_len // 4)
                ca, sa  = math.cos(0.45), math.sin(0.45)
                for hx, hy in [
                    (ex - head * (ux * ca + uy * sa), ey - head * (-ux * sa + uy * ca)),
                    (ex - head * (ux * ca - uy * sa), ey - head * (ux * sa  + uy * ca)),
                ]:
                    draw.line([(ex, ey), (int(hx), int(hy))], fill=(*rgb, 220), width=4)

        # ── Glow rings ────────────────────────────────────────────────────────
        for gr, ga in [(r + 14, 30), (r + 7, 65)]:
            tmp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(tmp).ellipse([px-gr, py-gr, px+gr, py+gr], fill=(*rgb, ga))
            layer = Image.alpha_composite(layer, tmp)
            draw  = ImageDraw.Draw(layer)

        # ── Main dot ──────────────────────────────────────────────────────────
        draw.ellipse([px-r, py-r, px+r, py+r],
                     fill=(*rgb, 235), outline=(255, 255, 255, 220), width=2)
        draw.text((px, py), str(num),
                  fill=(255, 255, 255, 255), font=font_num, anchor="mm")

        # ── Callout label ─────────────────────────────────────────────────────
        if lbl:
            go_right = px < w * 0.55
            line_len = max(55, w // 9)
            tip_x    = px + (r + line_len if go_right else -(r + line_len))
            tip_y    = py - r // 2
            draw.line([(px + (r if go_right else -r), py), (tip_x, tip_y)],
                      fill=(*rgb, 170), width=2)
            pad = 6
            try:
                bbox = draw.textbbox((0, 0), lbl, font=font_lbl)
                lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except AttributeError:
                lw, lh = int(len(lbl) * fsize_label * 0.6), fsize_label + 4
            bx1 = tip_x if go_right else tip_x - lw - pad * 2
            by1 = tip_y - lh // 2 - pad
            bx2, by2 = bx1 + lw + pad * 2, by1 + lh + pad * 2
            # Clamp
            if bx2 > w - 4: d = bx2 - (w-4); bx1 -= d; bx2 -= d
            if bx1 < 4:     d = 4 - bx1;     bx1 += d; bx2 += d
            if by1 < 4:     by1 = 4;          by2 = by1 + lh + pad*2
            if by2 > h - 4: by2 = h-4;        by1 = by2 - lh - pad*2
            tmp3 = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(tmp3).rectangle([bx1, by1, bx2, by2], fill=(8, 8, 8, 215))
            layer = Image.alpha_composite(layer, tmp3)
            draw  = ImageDraw.Draw(layer)
            draw.rectangle([bx1, by1, bx2, by2], outline=(*rgb, 200), width=1)
            draw.text((bx1 + pad, by1 + pad), lbl, fill=(*rgb, 230), font=font_lbl)

    # ── Score bar panel (bottom-right) ────────────────────────────────────────
    if scores:
        score_items = [
            scores.get("technique",         5),
            scores.get("body_position",     5),
            scores.get("spatial_awareness", 5),
            scores.get("decision_making",   5),
            scores.get("effort",            5),
        ]
        bar_w   = max(72, w // 9)
        bar_h   = max(5, h // 72)
        row_h   = bar_h + 8
        panel_h = len(score_items) * row_h + 12
        px0     = w - bar_w - 14
        py0     = h - panel_h - 10
        tmp4 = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(tmp4).rectangle(
            [px0 - 8, py0 - 6, w - 6, h - 6], fill=(5, 5, 5, 210)
        )
        layer = Image.alpha_composite(layer, tmp4)
        draw  = ImageDraw.Draw(layer)
        # Green brand bar at top of panel
        draw.rectangle([px0 - 8, py0 - 6, w - 6, py0 - 3], fill=(0, 255, 135, 210))
        for i, val in enumerate(score_items):
            y  = py0 + i * row_h + 2
            bc = (16, 185, 129) if val >= 8 else (245, 158, 11) if val >= 6 else (239, 68, 68)
            draw.rectangle([px0, y, px0 + bar_w, y + bar_h], fill=(26, 26, 26, 180))
            fill_w = max(2, int(bar_w * val / 10))
            draw.rectangle([px0, y, px0 + fill_w, y + bar_h], fill=(*bc, 220))

    return layer


# ── Score panel overlay (static, pre-built once per video) ────────────────────

def _build_score_overlay(w: int, h: int, scores: dict) -> "Image.Image":
    """Render just the score panel onto a transparent RGBA canvas."""
    from PIL import Image, ImageDraw
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if not scores:
        return layer
    score_items = [
        scores.get("technique",         5),
        scores.get("body_position",     5),
        scores.get("spatial_awareness", 5),
        scores.get("decision_making",   5),
        scores.get("effort",            5),
    ]
    bar_w   = max(72, w // 9)
    bar_h   = max(5, h // 72)
    row_h   = bar_h + 8
    panel_h = len(score_items) * row_h + 12
    px0     = w - bar_w - 14
    py0     = h - panel_h - 10
    tmp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).rectangle([px0 - 8, py0 - 6, w - 6, h - 6], fill=(5, 5, 5, 210))
    layer = Image.alpha_composite(layer, tmp)
    draw  = ImageDraw.Draw(layer)
    draw.rectangle([px0 - 8, py0 - 6, w - 6, py0 - 3], fill=(0, 255, 135, 210))
    for i, val in enumerate(score_items):
        y  = py0 + i * row_h + 2
        bc = (16, 185, 129) if val >= 8 else (245, 158, 11) if val >= 6 else (239, 68, 68)
        draw.rectangle([px0, y, px0 + bar_w, y + bar_h], fill=(26, 26, 26, 180))
        fill_w = max(2, int(bar_w * val / 10))
        draw.rectangle([px0, y, px0 + fill_w, y + bar_h], fill=(*bc, 220))
    return layer


# ── Per-frame tracked annotation overlay ──────────────────────────────────────

def _build_overlay_tracked(
    w: int, h: int, anns: list, dx: int, dy: int, frame_idx: int
) -> "Image.Image":
    """
    Like _build_overlay but shifts all annotation positions by (dx, dy) —
    the estimated player motion delta from the key frame — and adds a
    pulsing glow animation driven by frame_idx.
    """
    from PIL import Image, ImageDraw

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    r           = max(14, min(w, h) // 30)
    fsize_num   = max(12, r - 4)
    fsize_label = max(10, r - 6)
    font_num, font_lbl = _load_fonts(fsize_num, fsize_label)
    pulse = 0.60 + 0.40 * abs(math.sin(frame_idx * 0.06))

    for ann in anns[:6]:
        region = ann.get("region", "body").lower()
        sev    = ann.get("severity", "warning")
        num    = ann.get("number", 1)
        lbl    = ann.get("label", "")[:28]
        rgb    = _SEV_RGB.get(sev, _SEV_RGB["warning"])

        # Reference position from key frame, shifted by player motion delta
        # Position priority: 1) Claude x_pct/y_pct  2) skeleton joints  3) fallback
        _region_to_joints = {
            "head": ["head"], "upper_body": ["left_shoulder", "right_shoulder"],
            "left_arm": ["left_elbow", "left_wrist"], "right_arm": ["right_elbow", "right_wrist"],
            "torso": ["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
            "hips": ["left_hip", "right_hip"], "left_leg": ["left_knee"],
            "right_leg": ["right_knee"], "left_foot": ["left_ankle"],
            "right_foot": ["right_ankle"], "feet": ["left_ankle", "right_ankle"],
            "body": ["left_hip", "right_hip"],
        }
        if ann.get("x_pct") is not None and ann.get("y_pct") is not None:
            xv, yv = float(ann["x_pct"]), float(ann["y_pct"])
            if 0.02 < xv < 0.98 and 0.02 < yv < 0.98:   # reject edge defaults
                base_px, base_py = int(xv * w), int(yv * h)
            else:
                base_px, base_py = None, None
        else:
            base_px, base_py = None, None
        if base_px is None:
            # No skeleton available in tracked overlay — fall back to region defaults
            skel = {}
            joint_names = _region_to_joints.get(region, [])
            jdata = skel.get("joints", {})
            _pts = [(float(jdata[j]["x"]), float(jdata[j]["y"])) for j in joint_names
                    if j in jdata and float(jdata[j].get("x",-1)) > 0 and float(jdata[j].get("y",-1)) > 0]
            if _pts:
                base_px = int(sum(p[0] for p in _pts) / len(_pts) * w)
                base_py = int(sum(p[1] for p in _pts) / len(_pts) * h)
            else:
                fx, fy  = _REGION_FALLBACK.get(region, (0.5, 0.5))
                base_px = int(fx * w)
                base_py = int(fy * h)

        px = max(r + 4, min(w - r - 4, base_px + dx))
        py = max(r + 4, min(h - r - 4, base_py + dy))

        # ── Vector arrow ──────────────────────────────────────────────────────
        vec = ann.get("vector")
        if vec and isinstance(vec, dict):
            vdx = float(vec.get("dx", 0))
            vdy = float(vec.get("dy", 0))
            mag = math.sqrt(vdx * vdx + vdy * vdy)
            if mag > 0.05:
                arrow_len = max(50, min(w, h) // 5)
                ex = max(4, min(w - 4, int(px + (vdx / mag) * arrow_len)))
                ey = max(4, min(h - 4, int(py + (vdy / mag) * arrow_len)))
                draw.line([(px, py), (ex, ey)], fill=(*rgb, 220), width=4)
                adx, ady = ex - px, ey - py
                dist = math.sqrt(adx * adx + ady * ady) or 1
                ux, uy  = adx / dist, ady / dist
                head    = max(14, arrow_len // 4)
                ca, sa  = math.cos(0.45), math.sin(0.45)
                for hx, hy in [
                    (ex - head * (ux * ca + uy * sa), ey - head * (-ux * sa + uy * ca)),
                    (ex - head * (ux * ca - uy * sa), ey - head * (ux * sa  + uy * ca)),
                ]:
                    draw.line([(ex, ey), (int(hx), int(hy))], fill=(*rgb, 220), width=4)

        # ── Pulsing glow rings ────────────────────────────────────────────────
        ga_outer = int(30 * pulse)
        ga_inner = int(65 * pulse)
        for gr, ga in [(r + 14, ga_outer), (r + 7, ga_inner)]:
            tmp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(tmp).ellipse([px-gr, py-gr, px+gr, py+gr], fill=(*rgb, ga))
            layer = Image.alpha_composite(layer, tmp)
            draw  = ImageDraw.Draw(layer)

        # ── Main dot ──────────────────────────────────────────────────────────
        draw.ellipse([px-r, py-r, px+r, py+r],
                     fill=(*rgb, 235), outline=(255, 255, 255, 220), width=2)
        draw.text((px, py), str(num),
                  fill=(255, 255, 255, 255), font=font_num, anchor="mm")

        # ── Callout label ─────────────────────────────────────────────────────
        if lbl:
            go_right = px < w * 0.55
            line_len = max(55, w // 9)
            tip_x    = px + (r + line_len if go_right else -(r + line_len))
            tip_y    = py - r // 2
            draw.line([(px + (r if go_right else -r), py), (tip_x, tip_y)],
                      fill=(*rgb, 170), width=2)
            pad = 6
            try:
                bbox = draw.textbbox((0, 0), lbl, font=font_lbl)
                lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except AttributeError:
                lw, lh = int(len(lbl) * fsize_label * 0.6), fsize_label + 4
            bx1 = tip_x if go_right else tip_x - lw - pad * 2
            by1 = tip_y - lh // 2 - pad
            bx2, by2 = bx1 + lw + pad * 2, by1 + lh + pad * 2
            if bx2 > w - 4: d = bx2 - (w-4); bx1 -= d; bx2 -= d
            if bx1 < 4:     d = 4 - bx1;     bx1 += d; bx2 += d
            if by1 < 4:     by1 = 4;          by2 = by1 + lh + pad * 2
            if by2 > h - 4: by2 = h-4;        by1 = by2 - lh - pad * 2
            tmp3 = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(tmp3).rectangle([bx1, by1, bx2, by2], fill=(8, 8, 8, 215))
            layer = Image.alpha_composite(layer, tmp3)
            draw  = ImageDraw.Draw(layer)
            draw.rectangle([bx1, by1, bx2, by2], outline=(*rgb, 200), width=1)
            draw.text((bx1 + pad, by1 + pad), lbl, fill=(*rgb, 230), font=font_lbl)

    return layer


# ── Still image annotation ─────────────────────────────────────────────────────

def annotate_image(image_bytes: bytes, annotations: list,
                   skeleton: dict | None = None) -> bytes:
    from PIL import Image

    img   = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h  = img.size
    layer = _build_overlay(w, h, annotations, {}, skeleton=skeleton)
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
    coaching_persona: str = "⚽ Expert Coach (Default)",
    output_language: str = "🇬🇧 English",
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

    # Compress every frame to JPEG regardless of source format
    compressed_list = []
    for fb in image_list:
        compressed_list.append(_compress_frame(fb))
    image_list = compressed_list

    # Hard size guard — if total base64 payload still > 12 MB, compress harder
    total_bytes = sum(len(fb) for fb in image_list)
    if total_bytes > 12_000_000:
        image_list = [_compress_frame(fb, max_w=640, max_h=480, quality=55) for fb in image_list]
        total_bytes = sum(len(fb) for fb in image_list)

    # Absolute limit — if still too large, drop to 2 frames
    if total_bytes > 10_000_000:
        image_list = image_list[:2]

    print(f"[tactify] sending {len(image_list)} frames, total size: {sum(len(f) for f in image_list) // 1024}KB")

    # Precise joint detection per frame using dedicated Haiku call
    _frame_joints: dict[int, dict] = {}  # frame_idx -> joints dict
    for _fi, _fb in enumerate(image_list[:4]):  # max 4 frames to keep cost low
        _jdata = _locate_player_joints(_fb)
        if _jdata.get("player_found") and _jdata.get("joints"):
            _frame_joints[_fi] = _jdata["joints"]

    _persona_instructions = {
        "🔴 Jürgen Klopp — Intense & Emotional": (
            "COACHING PERSONA — Jürgen Klopp: You are passionate, intense, and emotionally connected to the player's journey. "
            "Use energetic language. Reference pressing, intensity, and collective effort. "
            "Celebrate strengths with genuine excitement ('That first touch — unbelievable!'). "
            "Frame errors as opportunities with energy ('This is where we get better together!'). "
            "Keep the language direct, punchy, and motivational. Use short powerful sentences."
        ),
        "🔵 Pep Guardiola — Tactical & Positional": (
            "COACHING PERSONA — Pep Guardiola: You are meticulous, positional, and obsessed with the details of space and timing. "
            "Focus on body orientation, positioning between lines, and the relationship between the player and space around them. "
            "Reference concepts like 'half-spaces', 'third man runs', 'pressing triggers', 'positional superiority'. "
            "Be precise and intellectual — explain WHY each position matters tactically. "
            "Tone: calm, serious, deeply analytical."
        ),
        "⚫ José Mourinho — Direct & Results-Focused": (
            "COACHING PERSONA — José Mourinho: You are pragmatic, direct, and focused entirely on winning. "
            "Cut straight to what costs points and what wins games. No sentiment — only results. "
            "Be blunt about errors ('This mistake costs you the goal. Fix it or you don't play.'). "
            "Praise only when it directly impacts the result. "
            "Reference defensive organisation, game management, and clinical execution. "
            "Tone: confident, authoritative, no-nonsense."
        ),
    }
    _persona_text = _persona_instructions.get(coaching_persona, "")

    _lang_map = {
        "🇪🇸 Spanish": "Spanish", "🇧🇷 Portuguese": "Portuguese (Brazilian)",
        "🇫🇷 French": "French", "🇩🇪 German": "German", "🇮🇹 Italian": "Italian",
    }
    _lang_name = next((v for k, v in _lang_map.items() if k in output_language), None)
    _lang_instruction = (
        f"\n\nCRITICAL: Write ALL coaching text (summary, notes, labels, cues, drill descriptions, "
        f"strengths, fix cards, pro reference note) in {_lang_name}. "
        f"JSON keys must stay in English. Only the VALUES of coaching text fields should be translated."
    ) if _lang_name else ""

    content = [
        {"type": "image",
         "source": {"type": "base64", "media_type": "image/jpeg", "data": _b64(fb)}}
        for fb in image_list
    ]
    _full_prompt = prompt + ("\n\n" + _persona_text if _persona_text else "") + _lang_instruction
    content.append({"type": "text", "text": _full_prompt})

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            messages=[{"role": "user", "content": content}],
        )
        data = _parse_json(response.content[0].text)
        if data is None:
            return {"success": False, "error": "Could not parse AI response. Please try again.",
                    "data": None, "annotated_image": None, "key_frames": [], "frames_analyzed": len(image_list)}

        # Patch annotation coordinates with precise joint detection results
        _region_to_joints = {
            "head": ["head"], "upper_body": ["left_shoulder", "right_shoulder"],
            "left_arm": ["left_elbow", "left_wrist"], "right_arm": ["right_elbow", "right_wrist"],
            "torso": ["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
            "hips": ["left_hip", "right_hip"], "left_leg": ["left_knee"],
            "right_leg": ["right_knee"], "left_foot": ["left_ankle"],
            "right_foot": ["right_ankle"], "feet": ["left_ankle", "right_ankle"],
            "body": ["left_hip", "right_hip"],
        }
        for ann in data.get("annotations", []):
            frame_idx = max(0, ann.get("frame", 1) - 1)
            joints = _frame_joints.get(frame_idx, _frame_joints.get(0, {}))
            if not joints:
                continue
            region = ann.get("region", "body").lower()
            joint_names = _region_to_joints.get(region, ["left_hip", "right_hip"])
            pts = [(float(joints[j]["x"]), float(joints[j]["y"]))
                   for j in joint_names if j in joints
                   and float(joints[j].get("x", -1)) > 0 and float(joints[j].get("y", -1)) > 0]
            if pts:
                ann["x_pct"] = sum(p[0] for p in pts) / len(pts)
                ann["y_pct"] = sum(p[1] for p in pts) / len(pts)
        # Also patch skeleton with precise joints if available
        if data.get("skeleton") and _frame_joints:
            best_frame = data["skeleton"].get("frame", 1) - 1
            precise = _frame_joints.get(best_frame, _frame_joints.get(0, {}))
            if precise:
                for jname, jval in precise.items():
                    if float(jval.get("x", -1)) > 0:
                        data["skeleton"].setdefault("joints", {})[jname] = jval

        anns     = data.get("annotations", [])
        skeleton = data.get("skeleton")          # single skeleton dict (best frame)
        skel_fn  = int(skeleton.get("frame", 1)) if skeleton else None

        annotated_image = None
        try:
            annotated_image = annotate_image(image_list[0], anns,
                                             skeleton=skeleton if skel_fn == 1 else None)
        except Exception:
            pass

        key_frames = []
        for frame_idx, fb in enumerate(image_list):
            frame_num  = frame_idx + 1
            frame_anns = [a for a in anns if a.get("frame", frame_num) == frame_num]
            if not frame_anns:
                frame_anns = anns
            # Apply skeleton only on the frame it was observed in
            frame_skel = skeleton if (skel_fn is not None and skel_fn == frame_num) else None
            try:
                key_frames.append(annotate_image(fb, frame_anns, skeleton=frame_skel))
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


def _assess_injury_risk(data: dict) -> list[dict]:
    """Assess injury risk from skeleton angles and body position score. Returns list of risk flags."""
    risks = []
    scores = data.get("scores", {})
    skeleton = data.get("skeleton", {})
    angles = skeleton.get("key_angles", [])
    body_score = scores.get("body_position", 7)

    # Low body position score = higher risk
    if body_score <= 4:
        risks.append({
            "area": "General Biomechanics",
            "level": "high",
            "note": "Poor body positioning patterns increase load on knee and ankle joints. Correct technique reduces injury risk significantly.",
            "icon": "🦵"
        })
    elif body_score <= 6:
        risks.append({
            "area": "Joint Load",
            "level": "medium",
            "note": "Body position mechanics could place uneven load on stabilising muscles. Monitor after high-intensity sessions.",
            "icon": "⚠️"
        })

    # Check angles for concerning values
    for ang in angles:
        deg = ang.get("degrees", 0)
        assessment = ang.get("assessment", "good")
        label_a = ang.get("label", "")
        if assessment == "error":
            if "knee" in label_a.lower() and (deg < 90 or deg > 170):
                risks.append({"area": f"Knee — {label_a}", "level": "high",
                               "note": f"Knee angle of {deg}° during this action is outside the safe range. Risk of ACL/meniscus stress.", "icon": "🦴"})
            elif "hip" in label_a.lower():
                risks.append({"area": f"Hip — {label_a}", "level": "medium",
                               "note": f"Hip angle of {deg}° may indicate compensation patterns that load the lower back.", "icon": "🔴"})

    if not risks:
        risks.append({"area": "No flags raised", "level": "clear",
                      "note": "No obvious biomechanical injury risk patterns detected in this footage. Keep monitoring technique under fatigue.", "icon": "✅"})
    return risks[:3]


# ── Coaching Audio Narration ───────────────────────────────────────────────────

def merge_audio_into_video(video_bytes: bytes, audio_bytes: bytes) -> bytes | None:
    """
    Merge coaching audio (MP3) into the video using ffmpeg.
    The video loops continuously so the full audio narration plays without cutoff.
    Returns merged MP4 bytes, or None if ffmpeg is unavailable.
    """
    import subprocess
    ffmpeg_bin = _ffmpeg_exe()
    if not ffmpeg_bin:
        return None

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tv:
        tv.write(video_bytes)
        vpath = tv.name
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as ta:
        ta.write(audio_bytes)
        apath = ta.name
    out_path = vpath + "_merged.mp4"

    try:
        r = subprocess.run(
            [ffmpeg_bin, "-y",
             "-stream_loop", "-1",   # loop video so coaching audio never outrun it
             "-i", vpath,
             "-i", apath,
             "-map", "0:v:0",        # video stream from looped input
             "-map", "1:a:0",        # audio from coaching MP3 only (drop original audio)
             "-c:v", "copy",         # copy video stream as-is (fast, no re-encode)
             "-c:a", "aac",
             "-b:a", "128k",
             "-shortest",            # stop when audio (coaching narration) ends
             "-movflags", "+faststart",
             out_path],
            capture_output=True, timeout=120,
        )
        if r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            with open(out_path, "rb") as f:
                return f.read()
        # Fallback: re-encode video if stream copy failed (e.g. HEVC input)
        r2 = subprocess.run(
            [ffmpeg_bin, "-y",
             "-stream_loop", "-1",
             "-i", vpath,
             "-i", apath,
             "-map", "0:v:0",
             "-map", "1:a:0",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
             "-c:a", "aac", "-b:a", "128k",
             "-shortest",
             "-movflags", "+faststart",
             out_path],
            capture_output=True, timeout=120,
        )
        if r2.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            with open(out_path, "rb") as f:
                return f.read()
        return None
    except Exception:
        return None
    finally:
        for p in [vpath, apath, out_path]:
            try: os.unlink(p)
            except OSError: pass


def create_annotated_video_simple(
    video_bytes: bytes,
    annotations: list,
    scores: dict,
    skeleton: dict | None = None,
    progress_callback=None,
) -> bytes | None:
    """
    Composite annotation overlays onto every video frame using imageio_ffmpeg.

    Uses lightweight per-frame motion tracking (low-res frame differencing) to
    shift annotation positions by how much the player has moved from the key
    frame — so dots and arrows follow the player rather than staying fixed.
    """
    try:
        import imageio_ffmpeg
        from PIL import Image, ImageChops
    except ImportError:
        return None

    vpath = out_path = writer = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tv:
            tv.write(video_bytes)
            vpath = tv.name
        out_path = vpath + "_annotated.mp4"

        # ── Read all frames ───────────────────────────────────────────────────
        gen      = imageio_ffmpeg.read_frames(vpath)
        meta     = next(gen)
        w, h     = meta["size"]
        fps      = float(meta.get("fps") or 25)
        duration = float(meta.get("duration") or 0.0)
        w = w - (w % 2)
        h = h - (h % 2)
        frames   = list(gen)
        gen.close()

        if not frames:
            return None

        n_frames = len(frames)

        # ── Build PIL images for all frames ───────────────────────────────────
        pil_frames = []
        for raw in frames:
            img = Image.frombytes("RGB", meta["size"], raw)
            if img.size != (w, h):
                img = img.crop((0, 0, w, h))
            pil_frames.append(img)

        # ── Lightweight per-frame player position tracking ────────────────────
        # Downsample to 128×72 for fast frame differencing
        TRACK_W, TRACK_H = 128, 72
        track_imgs = [
            img.resize((TRACK_W, TRACK_H), Image.BILINEAR).convert("L")
            for img in pil_frames
        ]

        def _motion_center(i):
            """Weighted centroid of pixels that changed between frames i-1 and i."""
            if i == 0:
                return None
            diff_data  = list(ImageChops.difference(track_imgs[i], track_imgs[i - 1]).getdata())
            threshold  = 20
            wx = wy = total = 0.0
            for idx, val in enumerate(diff_data):
                if val > threshold:
                    wx    += (idx % TRACK_W) * val
                    wy    += (idx // TRACK_W) * val
                    total += val
            if total < 300:
                return None
            return (int(wx / total * w / TRACK_W), int(wy / total * h / TRACK_H))

        raw_positions = [_motion_center(i) for i in range(n_frames)]

        # Forward-fill gaps
        last = (w // 2, h // 2)
        for i in range(n_frames):
            if raw_positions[i] is not None:
                last = raw_positions[i]
            else:
                raw_positions[i] = last

        # Backward-fill leading Nones
        first = next((p for p in raw_positions if p is not None), (w // 2, h // 2))
        for i in range(n_frames):
            if raw_positions[i] == (w // 2, h // 2):
                raw_positions[i] = first
            else:
                break

        # Smooth with rolling average (~0.25 s window) to remove jitter
        win = max(3, int(fps / 4))
        smoothed = []
        for i in range(n_frames):
            s = max(0, i - win // 2)
            e = min(n_frames, i + win // 2 + 1)
            xs = [raw_positions[j][0] for j in range(s, e)]
            ys = [raw_positions[j][1] for j in range(s, e)]
            smoothed.append((int(sum(xs) / len(xs)), int(sum(ys) / len(ys))))

        # ── Annotation groups and key-frame anchor positions ──────────────────
        frame_nums = sorted({ann.get("frame", 1) for ann in annotations})
        num_groups = max(frame_nums) if frame_nums else 1
        skel_fn    = int(skeleton.get("frame", 1)) if skeleton else None

        # Video frame index for each annotation key frame
        kf_vidx = {}
        for fn in range(1, num_groups + 1):
            if duration > 0:
                kf_vidx[fn] = min(int(duration * fn / (num_groups + 1) * fps), n_frames - 1)
            else:
                kf_vidx[fn] = min(n_frames * fn // (num_groups + 1), n_frames - 1)

        # Player center (smoothed) at each key frame — annotation anchor
        kf_player = {fn: smoothed[vi] for fn, vi in kf_vidx.items()}

        # Time boundaries for switching annotation groups
        if num_groups > 1 and duration > 0:
            key_times  = [duration * (g + 1) / (num_groups + 1) for g in range(num_groups)]
            boundaries = [0.0]
            for g in range(len(key_times) - 1):
                boundaries.append((key_times[g] + key_times[g + 1]) / 2)
            boundaries.append(duration + 1.0)
        else:
            boundaries = None

        def _group_for_frame(i: int) -> int:
            if boundaries is None:
                return 1
            t = i / fps
            for g in range(num_groups):
                if boundaries[g] <= t < boundaries[g + 1]:
                    return g + 1
            return num_groups

        # Pre-group annotations
        group_anns = {}
        for fn in range(1, num_groups + 1):
            fa = [a for a in annotations if a.get("frame", 1) == fn]
            group_anns[fn] = fa if fa else annotations

        # Static overlays built once
        skeleton_overlay = None
        if skeleton and skel_fn:
            try:
                skeleton_overlay = _draw_skeleton_layer(w, h, skeleton)
            except Exception:
                pass
        score_overlay = _build_score_overlay(w, h, scores) if scores else None

        # ── Write annotated frames ────────────────────────────────────────────
        writer = imageio_ffmpeg.write_frames(
            out_path, (w, h),
            pix_fmt_in="rgb24",
            pix_fmt_out="yuv420p",
            fps=fps,
            quality=6,
            codec="libx264",
            macro_block_size=1,
            output_params=["-movflags", "+faststart"],
        )
        writer.send(None)

        for i, img in enumerate(pil_frames):
            fn          = _group_for_frame(i)
            anns        = group_anns.get(fn, group_anns.get(1, []))
            curr_player = smoothed[i]
            ref_player  = kf_player.get(fn, (w // 2, h // 2))
            dx          = curr_player[0] - ref_player[0]
            dy          = curr_player[1] - ref_player[1]

            img_rgba = img.convert("RGBA")

            # Skeleton only for its key frame group
            if skeleton_overlay and skel_fn and fn == skel_fn:
                img_rgba = Image.alpha_composite(img_rgba, skeleton_overlay)

            # Tracked annotation overlay (dots/arrows follow player motion)
            ann_overlay = _build_overlay_tracked(w, h, anns, dx, dy, i)
            img_rgba    = Image.alpha_composite(img_rgba, ann_overlay)

            # Score panel (always bottom-right, static)
            if score_overlay:
                img_rgba = Image.alpha_composite(img_rgba, score_overlay)

            writer.send(img_rgba.convert("RGB").tobytes())

        writer.close()
        writer = None

        if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            with open(out_path, "rb") as f:
                return f.read()
        return None

    except Exception:
        import traceback
        traceback.print_exc()
        return None
    finally:
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass
        for p in [vpath, out_path]:
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass


def extract_moment_clip(
    video_bytes: bytes,
    frame_num: int,
    num_key_frames: int,
    clip_duration: float = 3.5,
) -> bytes | None:
    """
    Extract a short clip from the video around the timestamp of a specific key frame.
    frame_num: 1-based index matching the key frame numbering in analysis data.
    num_key_frames: total number of key frames extracted (usually 4).
    Returns MP4 bytes or None.
    """
    try:
        import imageio_ffmpeg
        import subprocess

        ffmpeg_bin = _ffmpeg_exe()
        if not ffmpeg_bin:
            return None

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tv:
            tv.write(video_bytes)
            vpath = tv.name
        out_path = vpath + "_clip.mp4"

        try:
            gen      = imageio_ffmpeg.read_frames(vpath)
            meta     = next(gen)
            gen.close()
            duration = float(meta.get("duration") or 0)
            if duration <= 0:
                return None

            # Timestamp matching _extract_frames: ts = duration * frame_num / (num_key_frames + 1)
            ts    = duration * frame_num / (num_key_frames + 1)
            start = max(0.0, ts - 1.2)

            result = subprocess.run(
                [ffmpeg_bin, "-y",
                 "-ss", f"{start:.3f}", "-i", vpath,
                 "-t", f"{clip_duration:.3f}",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-crf", "22", "-movflags", "+faststart", "-an",
                 out_path],
                capture_output=True, timeout=60,
            )
            if result.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 500:
                with open(out_path, "rb") as f:
                    return f.read()
            return None
        finally:
            for p in [vpath, out_path]:
                if p and os.path.exists(p):
                    try:
                        os.unlink(p)
                    except OSError:
                        pass
    except Exception:
        return None


def _build_coaching_script(data: dict, position: str) -> str:
    """Build a punchy, coach-voice narration script from analysis data."""
    pf        = data.get("priority_fix", {})
    best      = data.get("best_moment", {})
    worst     = data.get("worst_moment", {})
    fix_cards = data.get("fix_cards", [])
    strengths = data.get("strengths", [])
    ref       = data.get("pro_reference", {})
    summary   = data.get("summary", "")

    parts = []

    # Hook opening
    parts.append("Alright. Let's talk about what I saw.")
    if summary:
        parts.append(summary)

    # Priority fix — the core of the session
    if pf.get("title"):
        parts.append(f"One thing stands out above everything else: {pf['title']}.")
        if pf.get("what"):
            parts.append(pf["what"])
        if pf.get("why"):
            parts.append(f"Why does this matter? {pf['why']}")
        if pf.get("cue"):
            parts.append(f"Write this down. Your cue is: {pf['cue']}. Say it every rep.")

    # Best moment — give them something to build on
    if best.get("description"):
        parts.append(
            f"Now, here's the good news. Your best moment? {best['description']} "
            "That right there — that's the standard. That's what this can look like when you get it right."
        )

    # Worst moment — direct, specific, no softening
    if worst.get("what"):
        parts.append(f"But here's what cost you. {worst['what']}.")
        if worst.get("cause"):
            parts.append(f"The root cause: {worst['cause']}")
        if worst.get("effect"):
            parts.append(f"And in a real game, that means: {worst['effect']}")

    # Fix cards — crisp and direct
    if fix_cards:
        parts.append(f"I've got {min(len(fix_cards), 3)} specific corrections.")
        for i, card in enumerate(fix_cards[:3], 1):
            if card.get("mistake"):
                parts.append(f"Number {i}: {card['mistake']}.")
            if card.get("correction"):
                parts.append(card["correction"])
            if card.get("cue"):
                parts.append(f"Your cue: {card['cue']}.")

    # Strengths — brief, genuine
    if strengths:
        parts.append("Here's what you're actually doing well.")
        for s in strengths[:2]:
            parts.append(s)
        parts.append("Don't lose that. Build on it.")

    # Pro reference
    if ref.get("player"):
        player = ref["player"]
        team   = ref.get("team", "")
        note   = ref.get("note", "")
        ref_line = f"One player I want you to study: {player}"
        if team:
            ref_line += f" from {team}"
        ref_line += "."
        parts.append(ref_line)
        if note:
            parts.append(note)

    parts.append("Now get to work. I'll see you next session.")
    return "  ".join(parts)


def _tts_edge(script: str) -> bytes | None:
    """Generate natural-sounding audio using Microsoft edge-tts (neural voice)."""
    try:
        import asyncio
        import edge_tts

        async def _speak():
            communicate = edge_tts.Communicate(script, voice="en-US-GuyNeural")
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            buf.seek(0)
            return buf.read()

        return asyncio.run(_speak())
    except Exception:
        return None


def _tts_gtts(script: str) -> bytes | None:
    """Fallback TTS using gTTS."""
    try:
        from gtts import gTTS
        tts = gTTS(text=script, lang="en", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception:
        return None


def generate_coaching_audio(data: dict, position: str) -> bytes | None:
    """
    Generate a natural coaching narration as MP3 bytes.
    Tries edge-tts (Microsoft neural voice) first, falls back to gTTS.
    """
    script = _build_coaching_script(data, position)
    if not script.strip():
        return None
    return _tts_edge(script) or _tts_gtts(script)


def generate_training_plan(data: dict, position: str, age_group: str) -> dict | None:
    """
    Generate a personalised 7-day training plan based on analysis data.
    Returns a dict with week_goal and days list, or None on failure.
    """
    client = anthropic.Anthropic()
    scores = data.get("scores", {})
    priority_fix = data.get("priority_fix", "")
    fix_cards = data.get("fix_cards", [])

    prompt = f"""You are an expert soccer coach. Based on the following player analysis, create a personalised 7-day training plan targeting the player's weakest areas.

Player position: {position}
Age group: {age_group}
Scores: {json.dumps(scores)}
Priority fix: {priority_fix}
Fix cards: {json.dumps(fix_cards)}

Return ONLY valid JSON (no markdown fences) with this exact structure:
{{
  "week_goal": "One sentence goal for the week",
  "days": [
    {{
      "day": "Monday",
      "focus": "Short focus label",
      "duration": "45 min",
      "drills": [
        {{"name": "Drill name", "duration": "10 min", "reps": "3x10", "description": "How to do it"}}
      ],
      "rest": false
    }},
    {{
      "day": "Tuesday",
      "focus": "Short focus label",
      "duration": "45 min",
      "drills": [
        {{"name": "Drill name", "duration": "10 min", "reps": "3x10", "description": "How to do it"}}
      ],
      "rest": false
    }},
    {{
      "day": "Wednesday",
      "focus": "Rest",
      "duration": "0 min",
      "drills": [],
      "rest": true
    }},
    {{
      "day": "Thursday",
      "focus": "Short focus label",
      "duration": "45 min",
      "drills": [
        {{"name": "Drill name", "duration": "10 min", "reps": "3x10", "description": "How to do it"}}
      ],
      "rest": false
    }},
    {{
      "day": "Friday",
      "focus": "Short focus label",
      "duration": "45 min",
      "drills": [
        {{"name": "Drill name", "duration": "10 min", "reps": "3x10", "description": "How to do it"}}
      ],
      "rest": false
    }},
    {{
      "day": "Saturday",
      "focus": "Short focus label",
      "duration": "60 min",
      "drills": [
        {{"name": "Drill name", "duration": "15 min", "reps": "4x10", "description": "How to do it"}}
      ],
      "rest": false
    }},
    {{
      "day": "Sunday",
      "focus": "Rest",
      "duration": "0 min",
      "drills": [],
      "rest": true
    }}
  ]
}}

Tailor all drills specifically to the player's weakest areas identified in the scores and priority fix. Include 2-4 drills per active day."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_json(response.content[0].text)
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
