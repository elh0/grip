"""The share clip's looks: trails (the default) and hybrid, both built on markers.

Trails (Elliot's pick, 21 Oct): markers on hands, feet, hips and head, each leaving a short
fading trail of where it has just been. Trails live on the wall, so a phone pan doesn't
smear them; they're mapped back into each frame through the camera motion.

Hybrid: the climber's outline plus the same markers.

Chosen over the ball-and-stick skeleton on six test clips (21 Oct): the outline comes from
the body's own pixels (the pose model's segmentation), so it can't sit off the climber or
put an elbow in the wrong place, and the markers sit on the steadiest points we track:
hands, feet, hips and head. A ring round a hand or foot means it's resting on a hold.
Without a segmentation pass (no model file) the markers are drawn alone.
"""

from __future__ import annotations

import bisect
import logging
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import frames as fr
from .motion import _to_wall
from .pose import PoseFrame

log = logging.getLogger(__name__)

CONTACTS = ("left_wrist", "right_wrist", "left_ankle", "right_ankle")
TRAIL_S = 0.6          # how far back a trail reaches
TRAIL_PEAK = 180       # a trail's opacity at its head (markers are 255)
MASK_BLEND_S = 0.14   # masks either side of a frame within this are blended: no flicker


def segmentation(video: Path, model_path: str, work_dir: Path, fps: float, width: int,
                 end: float | None = None) -> dict[float, np.ndarray]:
    """Body masks (0..1, picture coordinates) by time. {} when the model can't run."""
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision
    except ImportError:
        return {}
    if not model_path or not Path(model_path).is_file() or model_path.endswith(".pt"):
        return {}
    try:
        lm = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
            base_options=mpt.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO, num_poses=1, output_segmentation_masks=True))
    except (OSError, RuntimeError) as exc:
        log.warning("outline skipped: %s", exc)
        return {}
    masks: dict[float, np.ndarray] = {}
    try:
        for f in fr.sample_frames(video, work_dir, fps, width, end=end, prefix="m"):
            r = lm.detect_for_video(mp.Image.create_from_file(str(f.path)), int(round(f.t * 1000)))
            if r.segmentation_masks:
                masks[round(f.t, 3)] = np.squeeze(
                    r.segmentation_masks[0].numpy_view()).astype(np.float32)
    finally:
        lm.close()
    return masks


def mask_at(masks: dict[float, np.ndarray], keys: list[float], t: float) -> np.ndarray | None:
    i = bisect.bisect_left(keys, t)
    near = [keys[j] for j in (i - 2, i - 1, i, i + 1)
            if 0 <= j < len(keys) and abs(keys[j] - t) <= MASK_BLEND_S]
    if not near:
        return None
    w = np.array([1.0 / (0.03 + abs(k - t)) for k in near])
    return sum(masks[k] * wi for k, wi in zip(near, w, strict=True)) / w.sum()


def outline(mask: np.ndarray, size: tuple[int, int]) -> tuple[Image.Image, Image.Image]:
    """A hairline round the body and a soft glow under it, as L masks at `size`."""
    w, h = size
    soft = max(1.0, w / 430)
    a = Image.fromarray((np.clip(mask, 0, 1) * 255).astype(np.uint8)).resize(size, Image.BILINEAR)
    a = a.filter(ImageFilter.GaussianBlur(soft)).point(lambda v: 255 if v > 127 else 0)
    k = max(3, int(round(w / 270)) | 1)
    edge = Image.fromarray((np.asarray(a.filter(ImageFilter.MaxFilter(k))).astype(np.int16)
                            - np.asarray(a)).clip(0, 255).astype(np.uint8))
    glow = edge.filter(ImageFilter.GaussianBlur(soft * 2)).point(lambda v: min(255, v * 2) // 2)
    return edge, glow


def resting(drawn: list[PoseFrame]) -> set[tuple[int, str]]:
    """(sample index, contact) pairs where a hand or foot sits still on the wall.

    steady.clean_poses pins a resting contact to one wall spot, so still means identical.
    """
    out = set()
    for k, pf in enumerate(drawn):
        for n in CONTACTS:
            q = pf.points.get(n)
            if not q or q.visibility < 0.5:
                continue
            here = _to_wall(pf.cam or [[1, 0, 0], [0, 1, 0]], q.x, q.y)
            for j in (k - 1, k + 1):
                if 0 <= j < len(drawn):
                    p2 = drawn[j].points.get(n)
                    if not p2 or p2.visibility < 0.5:
                        continue
                    there = _to_wall(drawn[j].cam or [[1, 0, 0], [0, 1, 0]], p2.x, p2.y)
                    if math.dist(here, there) < 1e-6:
                        out.add((k, n))
                        break
    return out


def markers(draw: ImageDraw.ImageDraw, size: tuple[int, int], pf: PoseFrame,
            rest: set[str], line: int, r: int, fill: int = 255) -> None:
    """Hands and feet as dots (a ring while resting), hips a small square, head a ring.
    `draw` is a single-channel mask; joints fade with their opacity."""
    w, h = size
    for n in CONTACTS:
        q = pf.points.get(n)
        if not q or q.visibility <= 0.02:
            continue
        x, y, v = q.x * w, q.y * h, int(round(fill * q.visibility))
        if n in rest:
            big, dot = r * 2.4, r * 0.5
            draw.ellipse([x - big, y - big, x + big, y + big], outline=v, width=line)
            draw.ellipse([x - dot, y - dot, x + dot, y + dot], fill=v)
        else:
            dot = r * 0.9
            draw.ellipse([x - dot, y - dot, x + dot, y + dot], fill=v)
    lh, rh = pf.points.get("left_hip"), pf.points.get("right_hip")
    if lh and rh and min(lh.visibility, rh.visibility) > 0.02:
        x, y = (lh.x + rh.x) / 2 * w, (lh.y + rh.y) / 2 * h
        s = r * 1.2
        draw.rectangle([x - s, y - s, x + s, y + s], outline=int(round(fill * min(
            lh.visibility, rh.visibility))), width=line)
    nose = pf.points.get("nose")
    if nose and nose.visibility > 0.02:
        x, y, s = nose.x * w, nose.y * h, r * 0.7
        draw.ellipse([x - s, y - s, x + s, y + s], outline=int(round(fill * nose.visibility)),
                     width=line)


def _hip(pf: PoseFrame) -> tuple[float, float, float] | None:
    lh, rh = pf.points.get("left_hip"), pf.points.get("right_hip")
    if not (lh and rh):
        return None
    return (lh.x + rh.x) / 2, (lh.y + rh.y) / 2, min(lh.visibility, rh.visibility)


def _point(pf: PoseFrame, name: str) -> tuple[float, float, float] | None:
    if name == "hip":
        return _hip(pf)
    q = pf.points.get(name)
    return (q.x, q.y, q.visibility) if q else None


def trails(draw: ImageDraw.ImageDraw, size: tuple[int, int], drawn: list[PoseFrame],
           sample_t: list[float], t: float, pf: PoseFrame, line: int) -> None:
    """Fading trails behind hands, feet and hips over the last TRAIL_S seconds.

    Each past sample goes to the wall through its own camera and comes back into this frame
    through the nearest sample's, so the trail stays where the limb was on the wall.
    """
    w, h = size
    lo = bisect.bisect_left(sample_t, t - TRAIL_S)
    hi = bisect.bisect_right(sample_t, t)
    if hi <= lo:
        return
    k = min(max(hi - 1, 0), len(drawn) - 1)
    cam_now = np.vstack([np.asarray(drawn[k].cam or [[1, 0, 0], [0, 1, 0]], float), [0, 0, 1]])
    back = np.linalg.inv(cam_now)[:2].tolist()
    for n in CONTACTS + ("hip",):
        pts = []
        for j in range(lo, hi):
            p = _point(drawn[j], n)
            if p and p[2] >= 0.5:
                wx, wy = _to_wall(drawn[j].cam or [[1, 0, 0], [0, 1, 0]], p[0], p[1])
                x, y = _to_wall(back, wx, wy)
                pts.append((x * w, y * h, sample_t[j]))
        now = _point(pf, n)
        if now and now[2] >= 0.5:
            pts.append((now[0] * w, now[1] * h, t))
        for (x0, y0, _), (x1, y1, t1) in zip(pts, pts[1:], strict=False):
            a = max(0.0, 1 - (t - t1) / TRAIL_S)
            draw.line([(x0, y0), (x1, y1)], fill=int(TRAIL_PEAK * a), width=line)
