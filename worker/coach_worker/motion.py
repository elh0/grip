"""Clean pose tracks for the rules: one climber, steady joints, wall coordinates, body units.

Raw pose is noisy in four ways that all used to turn into false flags:
- each frame is guessed on its own, so joints jitter by a good fraction of a forearm;
- a handheld phone pans, so the whole body "moves" when the climber is still;
- the model sometimes jumps to someone else walking past;
- x and y are fractions of a 16:9 frame, so the same distance reads differently across and up.

`build_track` fixes those: it drops frames that belong to another body, subtracts the camera's
own movement (when known), smooths every joint, and measures everything in torso lengths, so a
threshold means the same thing near or far, at any frame rate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .pose import MIN_VISIBILITY, POINTS, PoseFrame

TORSO_RANGE = (0.6, 1.6)   # a frame whose torso is outside this ratio of the clip's is someone else
MAX_JUMP_TORSOS = 1.2      # hips moving further than this between samples: a different body
SMOOTH_S = 0.2             # joints are smoothed over about this window
IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]


@dataclass
class Track:
    """Joint positions over time in wall coordinates. Units are torso lengths; y points down."""

    t: np.ndarray                      # (n,) seconds
    joints: dict[str, np.ndarray]      # name -> (n, 2), nan where the joint isn't seen
    torso: float                       # the clip's torso length in frame units (for drawing)

    @property
    def fps(self) -> float:
        return (len(self.t) - 1) / (self.t[-1] - self.t[0]) if len(self.t) > 1 else 0.0

    def speed(self, name: str) -> np.ndarray:
        """Torso lengths per second, nan where unknown."""
        p = self.joints[name]
        if len(p) < 2:
            return np.full(len(p), np.nan)
        dt = np.gradient(self.t)
        return np.hypot(*np.gradient(p, axis=0).T) / dt

    def mid(self, a: str, b: str) -> np.ndarray:
        return np.nanmean(np.stack([self.joints[a], self.joints[b]]), axis=0)


def _torso(pf: PoseFrame, aspect: float) -> float | None:
    ls, rs, lh, rh = (pf.visible(n) for n in
                      ("left_shoulder", "right_shoulder", "left_hip", "right_hip"))
    sh = [p for p in (ls, rs) if p]
    hp = [p for p in (lh, rh) if p]
    if not sh or not hp:
        return None
    sx, sy = sum(p.x for p in sh) / len(sh), sum(p.y for p in sh) / len(sh)
    hx, hy = sum(p.x for p in hp) / len(hp), sum(p.y for p in hp) / len(hp)
    return math.hypot((sx - hx) * aspect, sy - hy) or None


Camera = list  # per frame, a 2x3 matrix taking that frame's (x, y) to the first frame's


def _to_wall(m, x: float, y: float) -> tuple[float, float]:
    return (m[0][0] * x + m[0][1] * y + m[0][2], m[1][0] * x + m[1][1] * y + m[1][2])


def _same_body(frames: list[PoseFrame], cam: Camera, aspect: float
               ) -> list[int]:
    """Indices of frames that belong to the main climber."""
    torsos = [_torso(f, aspect) for f in frames]
    known = [x for x in torsos if x]
    if not known:
        return []
    ref = float(np.median(known))
    keep: list[int] = []
    last = None
    for i, (f, tl) in enumerate(zip(frames, torsos, strict=True)):
        if not tl or not TORSO_RANGE[0] <= tl / ref <= TORSO_RANGE[1]:
            continue
        hips = [p for p in (f.visible("left_hip"), f.visible("right_hip")) if p]
        if not hips:
            continue
        hx, hy = _to_wall(cam[i], sum(p.x for p in hips) / len(hips),
                          sum(p.y for p in hips) / len(hips))
        hx *= aspect
        if last is not None:
            j, lx, ly = last
            gap = max(1, i - j)
            if math.hypot(hx - lx, hy - ly) / ref > MAX_JUMP_TORSOS * min(gap, 3):
                continue
        last = (i, hx, hy)
        keep.append(i)
    return keep


# Side-on, the model often swaps left and right limbs for a frame or two: a still climber's
# feet then "jump" across each other. A foot and its ankle are un-swapped together.
OVERLAP = 0.35  # torso lengths: closer than this, the two sides can't be told apart
CHAINS = (("ankle", "foot"), ("knee",), ("wrist",), ("elbow",))


def _unswap(joints: dict[str, np.ndarray]) -> None:
    """Swap left/right back wherever swapping fits the last clear frame better.

    When the two sides overlap (feet together, legs crossing) a frame can't tell them apart,
    so it is never used as the reference for the frames after it.
    """
    for chain in CHAINS:
        left = np.stack([joints[f"left_{j}"] for j in chain], axis=1)    # (n, k, 2)
        right = np.stack([joints[f"right_{j}"] for j in chain], axis=1)
        ref_l = ref_r = None
        for i in range(len(left)):
            lt, rt = left[i], right[i]
            if np.isnan(lt).all() and np.isnan(rt).all():
                continue
            if np.isnan(lt).all() or np.isnan(rt).all():
                # one side hidden: give the one we see to whichever side it's nearest
                if ref_l is not None:
                    seen = rt if np.isnan(lt).all() else lt
                    to_l = np.nansum(np.hypot(*(seen - ref_l).T))
                    to_r = np.nansum(np.hypot(*(seen - ref_r).T))
                    if (seen is lt and to_r < 0.6 * to_l) or (seen is rt and to_l < 0.6 * to_r):
                        left[i], right[i] = rt.copy(), lt.copy()
                continue
            if ref_l is not None:
                keep = np.nansum(np.hypot(*(lt - ref_l).T)) + np.nansum(np.hypot(*(rt - ref_r).T))
                swap = np.nansum(np.hypot(*(rt - ref_l).T)) + np.nansum(np.hypot(*(lt - ref_r).T))
                if swap < 0.6 * keep:
                    left[i], right[i] = lt, rt = rt.copy(), lt.copy()
                elif keep >= 0.6 * swap and np.nanmean(np.hypot(*(lt - rt).T)) < OVERLAP:
                    continue  # can't tell the sides apart here
            ref_l, ref_r = lt.copy(), rt.copy()
        for k, j in enumerate(chain):
            joints[f"left_{j}"], joints[f"right_{j}"] = left[:, k], right[:, k]


def _smooth(a: np.ndarray, k: int) -> np.ndarray:
    """Centred median then mean over k samples, ignoring gaps."""
    if k < 3 or len(a) < 3:
        return a
    h = k // 2
    pad = np.pad(a, ((h, h), (0, 0)), constant_values=np.nan)
    win = np.lib.stride_tricks.sliding_window_view(pad, k, axis=0)  # (n, 2, k)
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(win, axis=-1)
            pad = np.pad(med, ((1, 1), (0, 0)), constant_values=np.nan)
            out = np.nanmean(np.lib.stride_tricks.sliding_window_view(pad, 3, axis=0), axis=-1)
    out[np.isnan(a).any(axis=1)] = np.nan  # don't invent joints across gaps
    return out


def build_track(frames: list[PoseFrame], aspect: float = 1.0,
                camera: Camera | None = None) -> Track | None:
    """`aspect` is frame width over height; `camera` from `camera_motion`, one per frame."""
    if len(frames) < 2:
        return None
    cam = camera or [IDENTITY] * len(frames)
    keep = _same_body(frames, cam, aspect)
    if len(keep) < 2:
        return None
    torso = float(np.median([_torso(frames[i], aspect) for i in keep]))
    t = np.array([frames[i].t for i in keep])
    fps = (len(t) - 1) / (t[-1] - t[0]) if t[-1] > t[0] else 1.0
    k = max(3, int(round(SMOOTH_S * fps)) | 1)
    raw: dict[str, np.ndarray] = {}
    for name in POINTS:
        a = np.full((len(keep), 2), np.nan)
        for row, i in enumerate(keep):
            p = frames[i].points.get(name)
            if p and p.visibility >= MIN_VISIBILITY:
                wx, wy = _to_wall(cam[i], p.x, p.y)
                a[row] = (wx * aspect / torso, wy / torso)
        raw[name] = a
    _unswap(raw)
    joints = {name: _smooth(a, k) for name, a in raw.items()}
    return Track(t=t, joints=joints, torso=torso)


def camera_motion(image_paths: list) -> Camera:
    """How the phone moved: per frame, the map from its picture to the first frame's.

    The wall fills most of the picture, so matching features between neighbouring frames and
    fitting a move, turn and zoom (with outliers such as the climber thrown out) measures the
    phone's own motion. Mapping joints through it puts them on the wall: a hand on a hold
    stays put however the phone pans. Frames that can't be matched keep the last estimate.
    """
    try:
        import cv2
    except ImportError:
        return [IDENTITY] * len(image_paths)
    orb = cv2.ORB_create(1500)
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    acc = np.eye(3)
    out: Camera = []
    prev = None
    for path in image_paths:
        im = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if im is None:
            out.append(acc[:2].tolist())
            continue
        h, w = im.shape
        kp, des = orb.detectAndCompute(im, None)
        if prev is not None and des is not None and prev[1] is not None:
            matches = matcher.match(prev[1], des)
            if len(matches) >= 12:
                src = np.float32([prev[0][m.queryIdx].pt for m in matches])
                dst = np.float32([kp[m.trainIdx].pt for m in matches])
                m, inliers = cv2.estimateAffinePartial2D(dst, src, method=cv2.RANSAC,
                                                         ransacReprojThreshold=3)
                if m is not None and inliers.sum() >= 10:
                    scale, unscale = np.diag([w, h, 1.0]), np.diag([1 / w, 1 / h, 1.0])
                    acc = acc @ (unscale @ np.vstack([m, [0, 0, 1]]) @ scale)
        out.append(acc[:2].tolist())
        prev = (kp, des)
    return out
