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
    cam: list | None = None    # 2x3 map from this frame's picture to the first frame's (the wall)
    # metres, the model's own 3D guess centred on the hips (z: towards the camera is negative)
    world: dict[str, tuple[float, float, float]] = field(default_factory=dict)

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
              line: int | None = None, r: int | None = None, opacity: bool = False) -> None:
    """Hairline wireframe, joints as open dots, and the centre-of-mass trail if given.

    No line from the weight to the floor: it reached outside the body and read as the
    tracker misfiring, so the drawing stays on the person. With `opacity` (a single-channel
    mask as `draw`, `fill` its full value), each joint's visibility is how strongly it's
    drawn, so a lost joint fades instead of vanishing.
    """
    w, h = size
    line = line or max(1, w // 400)
    r = r or max(3, w // 160)

    def get(name: str) -> tuple[Point, float] | None:
        if not opacity:
            p = pf.visible(name)
            return (p, 1.0) if p else None
        p = pf.points.get(name)
        return (p, p.visibility) if p and p.visibility > 0.02 else None

    def shade(a: float):
        return fill if not opacity else int(round(fill * a))

    def xy(p: Point) -> tuple[float, float]:
        return (p.x * w, p.y * h)

    if trail and len(trail) > 1:
        draw.line([(x * w, y * h) for x, y in trail], fill=fill, width=line, joint="curve")
    for a, b in BONES:
        pa, pb = get(a), get(b)
        if pa and pb:
            draw.line([xy(pa[0]), xy(pb[0])], fill=shade(min(pa[1], pb[1])), width=line)
    for name in POINTS:
        got = get(name)
        if got:
            x, y = xy(got[0])
            draw.ellipse([x - r, y - r, x + r, y + r], outline=shade(got[1]), width=line)


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
    """Thin wrapper over the MediaPipe Pose Landmarker.

    Video mode (the default) tracks the body from one frame to the next instead of guessing
    each frame afresh, which roughly halves the jitter. It needs frames in time order, so use
    one detector per clip.
    """

    # Heels for drawing feet (the rules don't use them); 3D for the tracking log.
    DETAIL = {"left_heel": 29, "right_heel": 30}
    WORLD = ("left_hip", "right_hip", "left_wrist", "right_wrist", "left_ankle", "right_ankle",
             "left_foot", "right_foot", "nose", "left_shoulder", "right_shoulder")
    CROP_PAD = 0.35       # crop: this much of the body's size added on every side
    CROP_MIN = 0.3        # crop: never narrower than this share of the frame

    def __init__(self, model_path: str, video: bool = True, crop: bool = False,
                 refine: bool = False):
        import mediapipe as mp  # optional dependency
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision

        self._mp = mp
        self._video = video
        self._crop = crop
        self._box: tuple[float, float, float, float] | None = None   # last body box, 0..1
        self._last_ms = -1
        options = vision.PoseLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.VIDEO if video else vision.RunningMode.IMAGE,
            num_poses=1,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        # refine: a second, single-image model looks again at just the climber and fills in
        # the hands and feet the tracking model is unsure of (it finds a lost limb in a
        # fraction of the time, but can't follow a body through bad light on its own)
        self._refiner = None
        if refine:
            self._refiner = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
                base_options=mp_tasks.BaseOptions(model_asset_path=model_path),
                running_mode=vision.RunningMode.IMAGE, num_poses=1))

    REFINE = ("left_wrist", "right_wrist", "left_ankle", "right_ankle", "left_foot",
              "right_foot", "left_heel", "right_heel", "left_elbow", "right_elbow",
              "left_knee", "right_knee")
    REFINE_AGREE = 0.6    # torso lengths: a second look further than this is someone else

    def _refine(self, image_path: Path, pf: PoseFrame) -> None:
        import numpy as np
        sure = [p for p in pf.points.values() if p.visibility >= 0.3]
        if len(sure) < 4:
            return
        x0, y0 = min(p.x for p in sure), min(p.y for p in sure)
        x1, y1 = max(p.x for p in sure), max(p.y for p in sure)
        side = max(max(x1 - x0, y1 - y0) * (1 + 2 * self.CROP_PAD), self.CROP_MIN)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        with Image.open(image_path) as im:
            rgb = im.convert("RGB")
            W, H = rgb.size
            px = (max(0, int((cx - side / 2) * W)), max(0, int((cy - side / 2) * H)),
                  min(W, int((cx + side / 2) * W)), min(H, int((cy + side / 2) * H)))
            cut = np.ascontiguousarray(np.asarray(rgb.crop(px)))
        r = self._refiner.detect(self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=cut))
        if not r.pose_landmarks:
            return
        lms = r.pose_landmarks[0]
        bx, by, bw, bh = px[0] / W, px[1] / H, (px[2] - px[0]) / W, (px[3] - px[1]) / H
        idx = {**POINTS, **self.DETAIL}
        ls, lh = pf.visible("left_shoulder"), pf.visible("left_hip")
        torso = math.hypot(ls.x - lh.x, ls.y - lh.y) if ls and lh else 0.2
        for n in self.REFINE:
            lm, old = lms[idx[n]], pf.points[n]
            v = getattr(lm, "visibility", 1.0) or 0.0
            x, y = bx + lm.x * bw, by + lm.y * bh
            near = math.hypot(x - old.x, y - old.y) < self.REFINE_AGREE * torso
            if v > old.visibility and (old.visibility < 0.3 or near):
                pf.points[n] = Point(x, y, v)

    def _run(self, image, t: float):
        if self._video:
            ms = max(int(round(t * 1000)), self._last_ms + 1)  # must strictly increase
            self._last_ms = ms
            return self._landmarker.detect_for_video(image, ms)
        return self._landmarker.detect(image)

    def _crop_box(self) -> tuple[float, float, float, float] | None:
        if not self._box:
            return None
        x0, y0, x1, y1 = self._box
        w, h = x1 - x0, y1 - y0
        side = max(w, h) * (1 + 2 * self.CROP_PAD)
        side = max(side, self.CROP_MIN)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        return (max(0.0, cx - side / 2), max(0.0, cy - side / 2),
                min(1.0, cx + side / 2), min(1.0, cy + side / 2))

    def detect(self, image_path: Path, t: float) -> PoseFrame | None:
        """Pose for one frame. With `crop`, the model looks only at the climber (plus room to
        move), found from the frame before, so small fast hands and feet get more pixels."""
        box = self._crop_box() if self._crop else None
        result = None
        if box:
            import numpy as np
            with Image.open(image_path) as im:
                rgb = im.convert("RGB")
                W, H = rgb.size
                px = (int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H))
                cut = np.ascontiguousarray(np.asarray(rgb.crop(px)))
            result = self._run(self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=cut), t)
            if result.pose_landmarks:
                bx0, by0 = px[0] / W, px[1] / H
                bw, bh = (px[2] - px[0]) / W, (px[3] - px[1]) / H
                for lm in result.pose_landmarks[0]:
                    lm.x, lm.y = bx0 + lm.x * bw, by0 + lm.y * bh
            else:
                result = None
        if result is None:
            result = self._run(self._mp.Image.create_from_file(str(image_path)), t)
        if not result.pose_landmarks:
            self._box = None
            return None
        lms = result.pose_landmarks[0]

        def vis(i: int) -> float:
            return getattr(lms[i], "visibility", 1.0) or 0.0

        points = {name: Point(lms[i].x, lms[i].y, vis(i))
                  for name, i in {**POINTS, **self.DETAIL}.items()}
        sure = [p for p in points.values() if p.visibility >= 0.3]
        if sure:
            self._box = (min(p.x for p in sure), min(p.y for p in sure),
                         max(p.x for p in sure), max(p.y for p in sure))
        pf = PoseFrame(t=t, points=points)
        if self._refiner:
            self._refine(image_path, pf)
        if result.pose_world_landmarks:
            wl = result.pose_world_landmarks[0]
            idx = {**POINTS, **self.DETAIL}
            pf.world = {n: (wl[idx[n]].x, wl[idx[n]].y, wl[idx[n]].z) for n in self.WORLD}
        return measure(pf)

    def close(self) -> None:
        self._landmarker.close()
        if self._refiner:
            self._refiner.close()


# COCO's 17 keypoints (YOLO pose) by index, for the fifteen points we use. COCO has no toe
# point, so the feet are left out and the ankles carry the foot.
COCO: dict[str, int] = {
    "nose": 0, "left_shoulder": 5, "right_shoulder": 6, "left_elbow": 7, "right_elbow": 8,
    "left_wrist": 9, "right_wrist": 10, "left_hip": 11, "right_hip": 12,
    "left_knee": 13, "right_knee": 14, "left_ankle": 15, "right_ankle": 16,
}


class YoloPoseDetector:
    """Ultralytics YOLO pose (a `.pt` model): finds every person, tracks each by id.

    It sees bodies whole even when side-on or half hidden, where MediaPipe drops the far arm
    or leg, so it suits climbing and, later, two bodies in BJJ. It locks onto the biggest
    person when it first sees one and follows that id; if the id is lost for a second it
    locks again. Licence: AGPL-3.0, so a closed app needs an Ultralytics licence.
    """

    RELOCK_S = 1.0

    def __init__(self, model_path: str, imgsz: int = 640):
        from ultralytics import YOLO  # optional dependency

        self._model = YOLO(model_path)
        self._imgsz = imgsz
        self._id: int | None = None
        self._seen_t = -1e9

    def detect(self, image_path: Path, t: float) -> PoseFrame | None:
        r = self._model.track(str(image_path), persist=True, verbose=False, imgsz=self._imgsz,
                              tracker="bytetrack.yaml")[0]
        if r.keypoints is None or not len(r.keypoints):
            return None
        kps = r.keypoints.data.cpu().numpy()
        boxes = r.boxes.xyxyn.cpu().numpy()
        ids = r.boxes.id.cpu().numpy().astype(int).tolist() if r.boxes.id is not None \
            else [None] * len(kps)
        pick = next((k for k, i in enumerate(ids) if i is not None and i == self._id), None)
        if pick is None:
            if t - self._seen_t < self.RELOCK_S and self._id is not None:
                return None  # our climber is briefly hidden; don't jump to someone else
            pick = max(range(len(kps)), key=lambda k: (boxes[k][2] - boxes[k][0])
                       * (boxes[k][3] - boxes[k][1]))
            self._id = ids[pick]
        self._seen_t = t
        h, w = r.orig_shape
        kp = kps[pick]
        points = {name: Point(0.0, 0.0, 0.0) for name in POINTS}
        for name, i in COCO.items():
            x, y, conf = kp[i]
            points[name] = Point(float(x) / w, float(y) / h, float(conf))
        return measure(PoseFrame(t=t, points=points))

    def close(self) -> None:
        self._model = None


def try_detector(model_path: str, video: bool = True, refine: bool = False):
    """The detector for a model file: `.pt` is YOLO pose, `.task` MediaPipe. None if unusable."""
    if not model_path or not Path(model_path).is_file():
        return None
    try:
        if model_path.endswith(".pt"):
            return YoloPoseDetector(model_path)
        return PoseDetector(model_path, video=video, refine=refine)
    except (ImportError, OSError) as exc:  # not installed, or Linux without libEGL/libGLES
        logging.getLogger(__name__).warning("pose disabled: %s", exc)
        return None
