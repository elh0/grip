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

from .pose import MIN_VISIBILITY, POINTS, Point, PoseFrame, measure

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


SHOW_FROM, HIDE_BELOW = 0.5, 0.3   # a joint appears once this sure, and goes once below this
FILL_GAP_S = 0.4                   # a joint lost for this long or less is drawn through the gap
BODY_SIGMA_S = 0.12                # head, shoulders, hips: they move slowly, so smooth hard
LIMB_SIGMA_S = 0.09                # elbows and knees
END_SIGMA_S = 0.06                 # hands and feet while they move: keep up with the climber
EASE_SIGMA_S = 0.04                # softens the step where a held hand starts to move
HOLD_SPEED = 0.7                   # torso lengths a second: slower than this, a hand or foot is
HOLD_MIN_S = 0.25                  #   on a hold, if it stays that slow for at least this long
ENDS = ("left_wrist", "right_wrist", "left_ankle", "right_ankle", "left_foot", "right_foot")
LIMBS = ("left_elbow", "right_elbow", "left_knee", "right_knee")
BONE_WINDOW_S = 1.0                # bone lengths are held to their median over about this long
JOINTS_3 = tuple((f"{s}_{a}", f"{s}_{b}", f"{s}_{c}") for s in ("left", "right")
                 for a, b, c in (("shoulder", "elbow", "wrist"), ("hip", "knee", "ankle")))


def _invert(m) -> np.ndarray:
    a = np.vstack([np.asarray(m, dtype=float), [0.0, 0.0, 1.0]])
    return np.linalg.inv(a)[:2]


def _hold(a: np.ndarray, fps: float) -> np.ndarray:
    """Pin a hand or foot to one spot for as long as it rests on a hold.

    The model's guess wanders a few pixels every frame even when a hand is clamped on a hold,
    and that wander is what makes a skeleton look unsure. In wall coordinates a resting hand
    doesn't move at all, so each still spell is replaced by its median position.
    """
    out = a.copy()
    seen = ~np.isnan(a[:, 0])
    if seen.sum() < 3:
        return out
    v = np.full(len(a), np.inf)
    d = np.gradient(np.where(seen[:, None], a, np.nan), axis=0) * fps
    v[seen] = np.hypot(d[seen, 0], d[seen, 1])
    still = np.nan_to_num(v, nan=np.inf) < HOLD_SPEED
    min_len = max(2, int(round(HOLD_MIN_S * fps)))
    i = 0
    while i < len(a):
        if not still[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(a) and still[j + 1]:
            j += 1
        if j - i + 1 >= min_len:
            out[i:j + 1] = np.nanmedian(a[i:j + 1], axis=0)
        i = j + 1
    return out


def _rolling_median(x: np.ndarray, k: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        w = x[max(0, i - k):i + k + 1]
        if np.any(~np.isnan(w)):
            out[i] = np.nanmedian(w)
    return out


def _rigid_limbs(smooth: dict[str, np.ndarray], fps: float, sigma: float) -> None:
    """Put each elbow and knee where its two bones, at steady lengths, meet.

    With the shoulder and hand both steady, what's left of the wobble is the elbow sliding
    about between them, which makes the arm look like it's stretching. Upper arm and forearm
    are held to their typical length over the last second or so (that still allows for a
    limb turning towards the camera), and the joint goes to whichever of the two possible
    meeting points is nearer the model's guess.
    """
    k = max(1, int(round(BONE_WINDOW_S * fps / 2)))
    for root, mid, end in JOINTS_3:
        a, b, c = smooth[root], smooth[mid], smooth[end]
        l1 = _rolling_median(np.hypot(*(b - a).T), k)
        l2 = _rolling_median(np.hypot(*(c - b).T), k)
        out = b.copy()
        for i in range(len(b)):
            if np.isnan(a[i]).any() or np.isnan(b[i]).any() or np.isnan(c[i]).any():
                continue
            d = float(np.hypot(*(c[i] - a[i])))
            r1, r2 = l1[i], l2[i]
            if d < 1e-9 or np.isnan(r1) or np.isnan(r2):
                continue
            u = (c[i] - a[i]) / d
            if d >= r1 + r2 or d <= abs(r1 - r2):       # can't meet: keep the guess
                continue
            x = (d * d + r1 * r1 - r2 * r2) / (2 * d)
            h = math.sqrt(max(0.0, r1 * r1 - x * x))
            base = a[i] + u * x
            n = np.array([-u[1], u[0]])
            p1, p2 = base + n * h, base - n * h
            out[i] = p1 if np.hypot(*(p1 - b[i])) <= np.hypot(*(p2 - b[i])) else p2
        smooth[mid] = _gauss(out, sigma)  # no step where a limb straightens past reach


def clean_poses(frames: list[PoseFrame], aspect: float = 1.0) -> list[PoseFrame]:
    """Poses for drawing: one body, left and right kept straight, steady, no flicker.

    Comes back in picture coordinates (the drawing goes on the picture), but the cleaning is
    done on the wall when the frames carry the phone's motion (`PoseFrame.cam`): hands and
    feet resting on holds are pinned still there, so the phone's panning can't shake them.
    Joints don't blink on and off as the model's confidence wobbles around the cut-off, short
    losses are bridged, and every joint is smoothed with a centred window (harder for the
    slow-moving trunk), so nothing lags behind the climber.
    """
    keep = _same_body(frames, [f.cam or IDENTITY for f in frames], aspect)
    if len(keep) < 2:
        return [frames[i] for i in keep]
    t = np.array([frames[i].t for i in keep])
    cams = [frames[i].cam or IDENTITY for i in keep]
    fps = (len(t) - 1) / (t[-1] - t[0]) if t[-1] > t[0] else 15.0
    torso = float(np.median([_torso(frames[i], aspect) for i in keep]))  # unswap thinks in torsos
    raw: dict[str, np.ndarray] = {}
    for name in POINTS:
        a = np.full((len(keep), 2), np.nan)
        shown = False
        for row, i in enumerate(keep):
            p = frames[i].points.get(name)
            v = p.visibility if p else 0.0
            shown = v >= (HIDE_BELOW if shown else SHOW_FROM)
            if shown:
                wx, wy = _to_wall(cams[row], p.x, p.y)
                a[row] = (wx * aspect / torso, wy / torso)
        raw[name] = _fill_gaps(a, max(1, int(round(FILL_GAP_S * fps))))
    _unswap(raw)

    def sig(s: float) -> float:
        return max(0.5, s * fps)

    smooth: dict[str, np.ndarray] = {}
    for name, a in raw.items():
        if name in ENDS:
            smooth[name] = _gauss(_hold(_gauss(a, sig(END_SIGMA_S)), fps), sig(EASE_SIGMA_S))
        else:
            smooth[name] = _gauss(a, sig(LIMB_SIGMA_S if name in LIMBS else BODY_SIGMA_S))
    _rigid_limbs(smooth, fps, sig(LIMB_SIGMA_S))
    back = [_invert(c) for c in cams]
    out = []
    for row, ti in enumerate(t):
        pts = {}
        for name, a in smooth.items():
            x, y = a[row]
            if np.isnan(x):
                pts[name] = Point(0.0, 0.0, 0.0)
                continue
            px, py = _to_wall(back[row], float(x * torso / aspect), float(y * torso))
            pts[name] = Point(px, py, 1.0)
        out.append(measure(PoseFrame(t=float(ti), points=pts, cam=cams[row])))
    return out


def _fill_gaps(a: np.ndarray, max_gap: int) -> np.ndarray:
    """Straight-line fill across nan runs of at most max_gap samples with data on both sides."""
    out = a.copy()
    seen = ~np.isnan(a[:, 0])
    idx = np.flatnonzero(seen)
    for i0, i1 in zip(idx, idx[1:], strict=False):
        if 1 < i1 - i0 <= max_gap + 1:
            u = (np.arange(i0 + 1, i1) - i0) / (i1 - i0)
            out[i0 + 1:i1] = a[i0] + (a[i1] - a[i0]) * u[:, None]
    return out


def _gauss(a: np.ndarray, sigma: float) -> np.ndarray:
    """Centred Gaussian smoothing over the samples that exist; gaps stay gaps."""
    r = max(1, int(math.ceil(2.5 * sigma)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    seen = ~np.isnan(a[:, 0])
    vals = np.where(seen[:, None], a, 0.0)
    num = np.stack([np.convolve(vals[:, j], k, mode="same") for j in range(2)], axis=1)
    den = np.convolve(seen.astype(float), k, mode="same")
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den[:, None]
    out[~seen] = np.nan
    return out


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
