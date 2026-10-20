"""The shareable clip: the whole climb with the blue tracking drawn on, and a small wordmark.

Every share is an ad, so it has to look good: pose runs at `POSE_FPS`, is cleaned
(motion.clean_poses: no blinking joints, short losses bridged, smoothed), interpolated to every
output frame at `OUTPUT_FPS`, and lines are drawn at twice the size
and scaled down so they stay clean after H.264. Capped at a minute and 1080 px on the long
side. Without pose there is nothing to show, so it is skipped.
"""

from __future__ import annotations

import bisect
import contextlib
import json
import logging
import math
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from . import frames as fr
from .motion import clean_poses
from .pose import MAT_BLUE, Point, PoseDetector, PoseFrame, draw_pose, measure, try_detector

log = logging.getLogger(__name__)

OUTPUT_FPS = 30
POSE_FPS = 15.0
POSE_WIDTH = 640              # what the pose model sees; it works at 256 px anyway
MAX_SECONDS = 60.0
MAX_SIDE = 1080
MAX_GAP_S = 0.5               # interpolate across a lost pose this short, otherwise draw nothing
MAX_JUMP = 0.1                # centre of mass moving further than this between samples: new body
SUPERSAMPLE = 2
WORDMARK_WHITE = (243, 243, 240)
WORDMARK_OPACITY = 0.85

# brand/grip-wordmark-white.svg, inlined because the worker image only ships coach_worker/.
_WORDMARK_VIEWBOX = (32, -787, 1660, 1019)
_WORDMARK_PATH = (
    "M304 232Q239 232 185.0 209.5Q131 187 94.5 144.5Q58 102 48 41H137Q151 91 196.5 122.5"
    "Q242 154 303 154Q351 154 389.0 133.5Q427 113 449.5 72.5Q472 32 472 -27V-98"
    "Q456 -71 429.5 -46.5Q403 -22 366.5 -6.5Q330 9 282 9Q212 9 155.0 -25.0Q98 -59 65.0 -117.5"
    "Q32 -176 32 -250Q32 -325 65.0 -383.0Q98 -441 155.0 -474.5Q212 -508 282 -508"
    "Q347 -508 396.5 -479.0Q446 -450 472 -410V-496H562V-30Q562 52 528.5 110.5"
    "Q495 169 436.5 200.5Q378 232 304 232ZM296 -69Q346 -69 385.0 -92.0Q424 -115 446.0 -156.0"
    "Q468 -197 468 -250Q468 -304 446.0 -344.5Q424 -385 385.0 -407.5Q346 -430 296 -430"
    "Q247 -430 208.0 -407.5Q169 -385 146.5 -344.5Q124 -304 124 -250Q124 -198 146.5 -156.5"
    "Q169 -115 208.0 -92.0Q247 -69 296 -69ZM650 0V-496H740V-418Q757 -457 786.0 -478.5"
    "Q815 -500 857 -500H931V-416H848Q816 -416 791.5 -398.0Q767 -380 753.5 -340.5"
    "Q740 -301 740 -236V0ZM1001 0V-496H1091V0ZM1177 220V-496H1267V-415"
    "Q1291 -451 1335.0 -479.5Q1379 -508 1447 -508Q1520 -508 1575.0 -474.0"
    "Q1630 -440 1661.0 -381.0Q1692 -322 1692 -247Q1692 -172 1661.0 -113.5"
    "Q1630 -55 1575.0 -21.5Q1520 12 1446 12Q1385 12 1339.0 -12.5Q1293 -37 1267 -81V220Z"
    "M1434 -66Q1483 -66 1520.5 -89.0Q1558 -112 1579.5 -153.0Q1601 -194 1601 -248"
    "Q1601 -302 1579.5 -343.0Q1558 -384 1520.5 -407.0Q1483 -430 1434 -430"
    "Q1386 -430 1348.5 -407.0Q1311 -384 1290.0 -343.0Q1269 -302 1269 -248"
    "Q1269 -194 1290.0 -153.0Q1311 -112 1348.5 -89.0Q1386 -66 1434 -66Z")
# The crimp over the i: a 90-wide round-capped stroke, two short legs and a half circle.
_CRIMP = {"cx": 1046, "cy": -658, "r": 84, "legs_to": -636, "stroke": 90}


@dataclass
class Source:
    duration: float
    width: int                # as displayed, after the phone's rotation flag
    height: int
    audio: str | None         # audio codec, if the clip has sound


def inspect(video: Path) -> Source:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(out)
    streams = data.get("streams", [])
    v = next(s for s in streams if s.get("codec_type") == "video")
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    rotation = float(v.get("tags", {}).get("rotate", 0) or 0)
    for side in v.get("side_data_list", []):
        rotation = float(side.get("rotation", rotation) or rotation)
    w, h = int(v["width"]), int(v["height"])
    if round(abs(rotation)) % 180 == 90:
        w, h = h, w
    return Source(duration=float(data["format"]["duration"]), width=w, height=h,
                  audio=a.get("codec_name") if a else None)


def output_size(width: int, height: int, max_side: int = MAX_SIDE) -> tuple[int, int]:
    """Fit the long side to max_side (never upscale), both sides even for yuv420p."""
    scale = min(1.0, max_side / max(width, height))
    return (max(2, round(width * scale / 2) * 2), max(2, round(height * scale / 2) * 2))


# -- pose over time ---------------------------------------------------------------------

def _mix(a: Point | None, b: Point | None, k: float) -> Point | None:
    if a and b:
        return Point(a.x + (b.x - a.x) * k, a.y + (b.y - a.y) * k, min(a.visibility, b.visibility))
    return a or b


def _jumped(a: tuple[float, float] | None, b: tuple[float, float] | None) -> bool:
    return bool(a and b and math.dist(a, b) > MAX_JUMP)


def _near(a: PoseFrame, b: PoseFrame, max_gap: float) -> bool:
    """Close enough in time and place to be the same body moving."""
    return abs(b.t - a.t) <= max_gap and not _jumped(a.com, b.com)


def pose_at(poses: list[PoseFrame], t: float, max_gap: float = MAX_GAP_S) -> PoseFrame | None:
    """The pose at time t: interpolated between samples, held briefly at the ends.

    Single-person tracking can hop to someone else in shot; never morph one body into another.
    """
    after = bisect.bisect_right(poses, t, key=lambda p: p.t)
    a = poses[after - 1] if after else None
    b = poses[after] if after < len(poses) else None
    if a and b and _near(a, b, max_gap):
        k = (t - a.t) / (b.t - a.t)
        names = a.points.keys() | b.points.keys()
        points = {n: _mix(a.visible(n), b.visible(n), k) or Point(0, 0, 0) for n in names}
        return measure(PoseFrame(t=t, points=points))
    near = min((p for p in (a, b) if p), key=lambda p: abs(p.t - t), default=None)
    if near and abs(near.t - t) <= max_gap / 2:
        return near
    return None


# -- wordmark ---------------------------------------------------------------------------

def _subpaths(d: str, steps: int = 8) -> list[list[tuple[float, float]]]:
    """Flatten an absolute M/Q/H/V/L/Z path (all the wordmark uses) into polygons."""
    tokens = re.findall(r"[A-Za-z]|-?\d+(?:\.\d+)?", d)
    polys: list[list[tuple[float, float]]] = []
    x = y = 0.0
    i = 0

    def num() -> float:
        nonlocal i
        i += 1
        return float(tokens[i - 1])

    while i < len(tokens):
        cmd = tokens[i]
        i += 1
        if cmd == "M":
            x, y = num(), num()
            polys.append([(x, y)])
        elif cmd == "L":
            x, y = num(), num()
            polys[-1].append((x, y))
        elif cmd == "H":
            x = num()
            polys[-1].append((x, y))
        elif cmd == "V":
            y = num()
            polys[-1].append((x, y))
        elif cmd == "Q":
            cx, cy, ex, ey = num(), num(), num(), num()
            for s in range(1, steps + 1):
                u = s / steps
                polys[-1].append(((1 - u) ** 2 * x + 2 * (1 - u) * u * cx + u * u * ex,
                                  (1 - u) ** 2 * y + 2 * (1 - u) * u * cy + u * u * ey))
            x, y = ex, ey
        elif cmd != "Z":
            raise ValueError(f"unsupported path command {cmd}")
    return polys


def wordmark(height: int, colour=WORDMARK_WHITE, opacity: float = WORDMARK_OPACITY
             ) -> Image.Image:
    """The grip wordmark as an RGBA image `height` px tall, rasterised from the brand path."""
    vx, vy, vw, vh = _WORDMARK_VIEWBOX
    ss = 4                                          # draw big, scale down for clean edges
    k = height * ss / vh
    size = (max(1, round(vw * k)), height * ss)

    def at(px: float, py: float) -> tuple[float, float]:
        return ((px - vx) * k, (py - vy) * k)

    mask = Image.new("L", size, 0)
    for poly in _subpaths(_WORDMARK_PATH):          # even-odd: counters cut out by xor
        layer = Image.new("L", size, 0)
        ImageDraw.Draw(layer).polygon([at(*p) for p in poly], fill=255)
        mask = ImageChops.difference(mask, layer)

    draw = ImageDraw.Draw(mask)
    c = _CRIMP
    half = c["stroke"] / 2 * k
    cx, cy = at(c["cx"], c["cy"])
    ro = c["r"] * k + half
    draw.arc([cx - ro, cy - ro, cx + ro, cy + ro], 180, 360, fill=255, width=round(half * 2))
    for lx in (c["cx"] - c["r"], c["cx"] + c["r"]):
        (x0, y0), (_, y1) = at(lx, c["cy"]), at(lx, c["legs_to"])
        draw.rectangle([x0 - half, y0, x0 + half, y1], fill=255)
        draw.ellipse([x0 - half, y1 - half, x0 + half, y1 + half], fill=255)

    mask = mask.resize((max(1, size[0] // ss), height), Image.LANCZOS)
    alpha = mask.point(lambda v: round(v * opacity))
    out = Image.new("RGBA", mask.size, (*colour, 0))
    out.putalpha(alpha)
    return out


# -- render -----------------------------------------------------------------------------

def track(video: Path, detector: PoseDetector, work_dir: Path, duration: float,
          pose_fps: float = POSE_FPS) -> list[PoseFrame]:
    sampled = fr.sample_frames(video, work_dir, pose_fps, POSE_WIDTH, end=duration, prefix="p")
    return [p for f in sampled if (p := detector.detect(f.path, f.t))]


def render_share(video: Path, out_path: Path, detector: PoseDetector | None, work_dir: Path, *,
                 poses: list[PoseFrame] | None = None,
                 fps: int = OUTPUT_FPS, pose_fps: float = POSE_FPS,
                 max_seconds: float = MAX_SECONDS, max_side: int = MAX_SIDE) -> Path | None:
    """Render the tracked clip to out_path. None when no body was found in the clip.

    Pass the review's `poses` to reuse its tracking; otherwise `detector` tracks the clip.
    """
    src = inspect(video)
    duration = min(src.duration, max_seconds)
    if not poses and detector:
        poses = track(video, detector, work_dir / "pose", duration, pose_fps)
    poses = clean_poses([p for p in poses or [] if p.t <= duration], src.width / src.height)
    if not poses:
        log.info("share skipped: no body tracked in %s", video.name)
        return None

    w, h = output_size(src.width, src.height, max_side)
    short = min(w, h)
    line = max(2, round(max(w, h) / 540)) * SUPERSAMPLE
    r = max(4, round(max(w, h) / 200)) * SUPERSAMPLE
    mark = wordmark(max(12, round(short * 0.07)))
    margin = max(6, round(short * 0.045))
    mark_box = (w - mark.width - margin, h - mark.height - margin)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    decode = ["ffmpeg", "-v", "error", "-i", str(video), "-t", f"{duration:.3f}",
              "-vf", f"fps={fps},scale={w}:{h}:flags=lanczos",
              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    encode = ["ffmpeg", "-v", "error", "-y",
              "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    if src.audio:
        encode += ["-i", str(video), "-map", "0:v:0", "-map", "1:a:0"]
        encode += ["-c:a", "copy"] if src.audio == "aac" else ["-c:a", "aac", "-b:a", "128k"]
    encode += ["-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)]

    frame_bytes = w * h * 3
    with tempfile.TemporaryFile() as dec_err, tempfile.TemporaryFile() as enc_err:
        dec = subprocess.Popen(decode, stdout=subprocess.PIPE, stderr=dec_err)
        enc = subprocess.Popen(encode, stdin=subprocess.PIPE, stderr=enc_err)
        try:
            i = 0
            while len(raw := dec.stdout.read(frame_bytes)) == frame_bytes:
                t = i / fps
                im = Image.frombytes("RGB", (w, h), raw)
                pf = pose_at(poses, t)
                if pf:
                    # no centre-of-mass trail: in picture coordinates it lags off the hip
                    # whenever the phone pans, and reads as the tracker losing the body
                    mask = Image.new("L", (w * SUPERSAMPLE, h * SUPERSAMPLE), 0)
                    draw_pose(ImageDraw.Draw(mask), mask.size, pf, fill=255,
                              line=line, r=r)
                    im.paste(MAT_BLUE, mask=mask.reduce(SUPERSAMPLE))
                im.paste(mark, mark_box, mark)
                try:
                    enc.stdin.write(im.tobytes())
                except BrokenPipeError:         # the encoder died; its log says why
                    dec.kill()
                    break
                i += 1
        finally:
            dec.stdout.close()
            with contextlib.suppress(BrokenPipeError):
                enc.stdin.close()
            dec_code, enc_code = dec.wait(), enc.wait()
        if dec_code or enc_code or i == 0:
            dec_err.seek(0)
            enc_err.seek(0)
            detail = (dec_err.read() + enc_err.read()).decode(errors="replace")[-1000:]
            raise RuntimeError(f"share render failed ({dec_code}/{enc_code}, {i} frames): "
                               f"{detail}")
    return out_path


def make_share(video: Path, out_path: Path, model_path: str, work_dir: Path,
               poses: list[PoseFrame] | None = None, **render_kw) -> Path | None:
    """Render the share if pose is available. None (and a log line) when it can't be made."""
    if poses:
        return render_share(video, out_path, None, work_dir, poses=poses, **render_kw)
    detector = try_detector(model_path)
    if not detector:
        log.info("share skipped: pose unavailable (set POSE_MODEL_PATH, install .[pose])")
        return None
    try:
        return render_share(video, out_path, detector, work_dir, **render_kw)
    finally:
        detector.close()
