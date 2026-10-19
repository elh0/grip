"""Optional pose: fifteen points, joint angles, centre of mass, and the blue wireframe.

MediaPipe is optional (pip install -e ".[pose]" and set POSE_MODEL_PATH). Everything
below `PoseDetector` is plain maths so it can be tested without it.
BJJ: tangled bodies break single-person tracking, so for rolls the athlete's note
("I'm in the blue gi") tells the coach who to review.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw

MAT_BLUE = (74, 116, 255)

# The fifteen points from the identity, mapped to MediaPipe's 33 landmark indices.
POINTS: dict[str, int] = {
    "nose": 0,
    "left_shoulder": 11, "right_shoulder": 12,
    "left_elbow": 13, "right_elbow": 14,
    "left_wrist": 15, "right_wrist": 16,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
    "left_foot": 31, "right_foot": 32,
}

BONES: list[tuple[str, str]] = [
    ("left_shoulder", "right_shoulder"), ("left_hip", "right_hip"),
    ("left_shoulder", "left_hip"), ("right_shoulder", "right_hip"),
    ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
    ("left_hip", "left_knee"), ("left_knee", "left_ankle"), ("left_ankle", "left_foot"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"), ("right_ankle", "right_foot"),
]

ANGLES: dict[str, tuple[str, str, str]] = {
    "left_elbow": ("left_shoulder", "left_elbow", "left_wrist"),
    "right_elbow": ("right_shoulder", "right_elbow", "right_wrist"),
    "left_knee": ("left_hip", "left_knee", "left_ankle"),
    "right_knee": ("right_hip", "right_knee", "right_ankle"),
    "left_hip": ("left_shoulder", "left_hip", "left_knee"),
    "right_hip": ("right_shoulder", "right_hip", "right_knee"),
}

MIN_VISIBILITY = 0.5


@dataclass
class Point:
    x: float  # normalised 0..1, left to right
    y: float  # normalised 0..1, top to bottom
    visibility: float = 1.0


@dataclass
class PoseFrame:
    t: float
    points: dict[str, Point]
    angles: dict[str, float] = field(default_factory=dict)
    com: tuple[float, float] | None = None

    def visible(self, name: str) -> Point | None:
        p = self.points.get(name)
        return p if p and p.visibility >= MIN_VISIBILITY else None


def angle(a: Point, b: Point, c: Point) -> float:
    """Angle at b in degrees (180 = straight)."""
    v1 = (a.x - b.x, a.y - b.y)
    v2 = (c.x - b.x, c.y - b.y)
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return float("nan")
    cos = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cos))


def centre_of_mass(pf: PoseFrame) -> tuple[float, float] | None:
    """Rough centre of mass: weighted mean of hips (heavy) and shoulders."""
    weighted = [("left_hip", 2.0), ("right_hip", 2.0), ("left_shoulder", 1.0),
                ("right_shoulder", 1.0)]
    xs = ys = total = 0.0
    for name, w in weighted:
        p = pf.visible(name)
        if p:
            xs += p.x * w
            ys += p.y * w
            total += w
    return (xs / total, ys / total) if total else None


def measure(pf: PoseFrame) -> PoseFrame:
    for name, (a, b, c) in ANGLES.items():
        pa, pb, pc = pf.visible(a), pf.visible(b), pf.visible(c)
        if pa and pb and pc:
            pf.angles[name] = round(angle(pa, pb, pc), 1)
    pf.com = centre_of_mass(pf)
    return pf


def draw_pose(draw: ImageDraw.ImageDraw, size: tuple[int, int], pf: PoseFrame,
              trail: list[tuple[float, float]] | None = None, fill=MAT_BLUE,
              line: int | None = None, r: int | None = None) -> None:
    """Hairline wireframe, joints as open dots, the centre-of-mass trail and centre line."""
    w, h = size
    line = line or max(1, w // 400)
    r = r or max(3, w // 160)

    def xy(p: Point) -> tuple[float, float]:
        return (p.x * w, p.y * h)

    if trail and len(trail) > 1:
        draw.line([(x * w, y * h) for x, y in trail], fill=fill, width=line, joint="curve")
    for a, b in BONES:
        pa, pb = pf.visible(a), pf.visible(b)
        if pa and pb:
            draw.line([xy(pa), xy(pb)], fill=fill, width=line)
    for name in POINTS:
        p = pf.visible(name)
        if p:
            x, y = xy(p)
            draw.ellipse([x - r, y - r, x + r, y + r], outline=fill, width=line)
    if pf.com:
        x, y = pf.com[0] * w, pf.com[1] * h
        # centre line: dropped from the weight to the floor
        draw.line([(x, y), (x, h)], fill=fill, width=line)


def draw_wireframe(image_path: Path, pf: PoseFrame, out_path: Path,
                   trail: list[tuple[float, float]] | None = None) -> Path:
    """The wireframe drawn onto a keyframe."""
    with Image.open(image_path) as src:
        im = src.convert("RGB")
    draw_pose(ImageDraw.Draw(im), im.size, pf, trail)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path, quality=88)
    return out_path


class PoseDetector:
    """Thin wrapper over the MediaPipe Pose Landmarker (image mode)."""

    def __init__(self, model_path: str):
        import mediapipe as mp  # optional dependency
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision

        self._mp = mp
        options = vision.PoseLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)

    def detect(self, image_path: Path, t: float) -> PoseFrame | None:
        image = self._mp.Image.create_from_file(str(image_path))
        result = self._landmarker.detect(image)
        if not result.pose_landmarks:
            return None
        lms = result.pose_landmarks[0]
        points = {
            name: Point(lms[i].x, lms[i].y, getattr(lms[i], "visibility", 1.0) or 0.0)
            for name, i in POINTS.items()
        }
        return measure(PoseFrame(t=t, points=points))

    def close(self) -> None:
        self._landmarker.close()


def try_detector(model_path: str) -> PoseDetector | None:
    if not model_path or not Path(model_path).is_file():
        return None
    try:
        return PoseDetector(model_path)
    except (ImportError, OSError) as exc:  # not installed, or Linux without libEGL/libGLES
        logging.getLogger(__name__).warning("pose disabled: %s", exc)
        return None
