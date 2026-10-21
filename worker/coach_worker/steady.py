"""Poses for drawing: steady, never frozen, never a ghost.

Grip is a measuring tool, so the drawing has to look sure of itself. Raw pose fails that in
three ways: joints jitter every frame, a hand the model loses for a moment either blinks
out or sticks where it last was, and a joint lost for good leaves a ghost behind. This
cleans each joint on the wall (the phone's own motion taken out) in four steps:

1. Gaps: a constant-velocity Kalman filter runs forwards and is smoothed backwards (RTS),
   so a short loss is predicted from how the joint was moving, weighted by the model's
   confidence in every frame. Nothing is ever held at a stale position.
2. Fade: a joint lost for longer than `lost_s` fades out over `fade_s`, and fades back in
   just before the model finds it again, instead of hanging in the air.
3. Smoothing: a One Euro filter (steady when still, quick on fast moves), run both ways so
   it doesn't lag. `min_cutoff` and `beta` tune it.
4. Holds: a hand or foot the model sees resting on a hold is pinned there; elbows and knees
   sit where their two bones meet at steady lengths.

Everything comes back in picture coordinates with `Point.visibility` as the drawing's
opacity (0..1). It is only for drawing: the rules use `motion.build_track`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .motion import IDENTITY, _same_body, _to_wall, _torso, _unswap
from .pose import POINTS, Point, PoseFrame, measure

DETAIL = {"left_heel": 29, "right_heel": 30}   # drawn when the model gives them; rules ignore them
ENDS = ("left_wrist", "right_wrist", "left_ankle", "right_ankle", "left_foot", "right_foot",
        "left_heel", "right_heel")
LIMBS = ("left_elbow", "right_elbow", "left_knee", "right_knee")
JOINTS_3 = tuple((f"{s}_{a}", f"{s}_{b}", f"{s}_{c}") for s in ("left", "right")
                 for a, b, c in (("shoulder", "elbow", "wrist"), ("hip", "knee", "ankle")))


@dataclass
class Tuning:
    show_from: float = 0.5      # a joint counts as seen once the model is this sure
    hide_below: float = 0.3     # ...and stops counting below this
    meas_noise: float = 0.04    # torso lengths: the model's typical error at full confidence
    accel_noise: float = 30.0   # torso lengths/s²: how hard a limb can change speed
    lost_s: float = 0.3         # a gap longer than this fades out...
    fade_s: float = 0.25        # ...over this long
    fade_in_s: float = 0.12     # and fades back in over this long as the joint is found
    min_cutoff: float = 0.6     # One Euro: Hz of smoothing when still (lower = steadier)
    beta: float = 1.5           # One Euro: how fast smoothing relaxes with speed
    d_cutoff: float = 1.0       # One Euro: Hz, smoothing of the speed estimate
    pin_holds: bool = True
    hold_speed: float = 0.7     # torso lengths/s: slower than this is resting on a hold...
    hold_min_s: float = 0.25    # ...for at least this long
    rigid_limbs: bool = True
    bone_window_s: float = 1.0


def kalman_rts(t: np.ndarray, z: np.ndarray, conf: np.ndarray, tu: Tuning) -> np.ndarray:
    """Constant-velocity Kalman over one coordinate, smoothed backwards. nan in z = unseen.

    Returns positions for every sample: measured ones are corrected, unseen ones predicted
    from both sides. Before the first and after the last measurement there is nothing to
    predict from, so those stay nan.
    """
    n = len(t)
    seen = ~np.isnan(z)
    out = np.full(n, np.nan)
    if seen.sum() == 0:
        return out
    first, last = np.flatnonzero(seen)[[0, -1]]
    xs, ps = np.zeros((n, 2)), np.zeros((n, 2, 2))      # filtered
    xp, pp = np.zeros((n, 2)), np.zeros((n, 2, 2))      # predicted
    x, p = np.array([z[first], 0.0]), np.diag([tu.meas_noise ** 2, 4.0])
    q = tu.accel_noise ** 2
    for i in range(first, last + 1):
        dt = t[i] - t[i - 1] if i > first else 0.0
        f = np.array([[1.0, dt], [0.0, 1.0]])
        qm = q * np.array([[dt ** 4 / 4, dt ** 3 / 2], [dt ** 3 / 2, dt ** 2]])
        x, p = f @ x, f @ p @ f.T + qm
        xp[i], pp[i] = x, p
        if seen[i]:
            r = (tu.meas_noise / max(conf[i], 0.2)) ** 2
            s = p[0, 0] + r
            k = p[:, 0] / s
            x = x + k * (z[i] - x[0])
            p = p - np.outer(k, p[0])
        xs[i], ps[i] = x, p
    for i in range(last - 1, first - 1, -1):
        dt = t[i + 1] - t[i]
        f = np.array([[1.0, dt], [0.0, 1.0]])
        c = ps[i] @ f.T @ np.linalg.inv(pp[i + 1])
        xs[i] = xs[i] + c @ (xs[i + 1] - xp[i + 1])
        ps[i] = ps[i] + c @ (ps[i + 1] - pp[i + 1]) @ c.T
    out[first:last + 1] = xs[first:last + 1, 0]
    return out


def _one_euro(t: np.ndarray, x: np.ndarray, tu: Tuning) -> np.ndarray:
    out = x.copy()
    prev = dprev = None
    for i in range(len(x)):
        if np.isnan(x[i]):
            prev = dprev = None
            continue
        if prev is None:
            prev, dprev, tp = x[i], 0.0, t[i]
            continue
        dt = max(t[i] - tp, 1e-3)
        a_d = 1.0 / (1.0 + 1.0 / (2 * math.pi * tu.d_cutoff * dt))
        dx = (x[i] - prev) / dt
        dprev = dprev + a_d * (dx - dprev)
        cutoff = tu.min_cutoff + tu.beta * abs(dprev)
        a = 1.0 / (1.0 + 1.0 / (2 * math.pi * cutoff * dt))
        prev = prev + a * (x[i] - prev)
        out[i], tp = prev, t[i]
    return out


def one_euro(t: np.ndarray, x: np.ndarray, tu: Tuning) -> np.ndarray:
    """One Euro filter run forwards and backwards and averaged, so it doesn't lag."""
    fwd = _one_euro(t, x, tu)
    bwd = _one_euro(-t[::-1], x[::-1], tu)[::-1]
    return (fwd + bwd) / 2


def _opacity(t: np.ndarray, seen: np.ndarray, tu: Tuning) -> np.ndarray:
    """1 while seen or briefly lost; fades out in a long gap and back in as it's found."""
    n = len(t)
    since = np.full(n, np.inf)   # seconds since last seen
    until = np.full(n, np.inf)   # seconds until next seen
    last = None
    for i in range(n):
        if seen[i]:
            last = t[i]
        if last is not None:
            since[i] = t[i] - last
    nxt = None
    for i in range(n - 1, -1, -1):
        if seen[i]:
            nxt = t[i]
        if nxt is not None:
            until[i] = nxt - t[i]
    gap = since + until
    out = np.ones(n)
    long_gap = gap > tu.lost_s
    fade_out = np.clip(1 - (since - tu.lost_s) / tu.fade_s, 0, 1)
    fade_in = np.clip(1 - until / tu.fade_in_s, 0, 1)
    out[long_gap] = np.maximum(fade_out, fade_in)[long_gap]
    return out


def _hold(t: np.ndarray, a: np.ndarray, seen: np.ndarray, tu: Tuning) -> np.ndarray:
    """Pin a hand or foot to one spot while the model sees it resting on a hold."""
    out = a.copy()
    if len(a) < 3:
        return out
    d = np.gradient(a, t, axis=0)
    v = np.hypot(d[:, 0], d[:, 1])
    still = (np.nan_to_num(v, nan=np.inf) < tu.hold_speed) & seen
    i = 0
    while i < len(a):
        if not still[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(a) and still[j + 1]:
            j += 1
        if t[j] - t[i] >= tu.hold_min_s:
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


def _rigid_limbs(j: dict[str, np.ndarray], fps: float, tu: Tuning) -> None:
    """Put each elbow and knee where its two bones, at steady lengths, meet."""
    k = max(1, int(round(tu.bone_window_s * fps / 2)))
    for root, mid, end in JOINTS_3:
        a, b, c = j[root], j[mid], j[end]
        l1 = _rolling_median(np.hypot(*(b - a).T), k)
        l2 = _rolling_median(np.hypot(*(c - b).T), k)
        out = b.copy()
        for i in range(len(b)):
            if np.isnan(a[i]).any() or np.isnan(b[i]).any() or np.isnan(c[i]).any():
                continue
            d = float(np.hypot(*(c[i] - a[i])))
            r1, r2 = l1[i], l2[i]
            if d < 1e-9 or np.isnan(r1) or np.isnan(r2) or d >= r1 + r2 or d <= abs(r1 - r2):
                continue
            u = (c[i] - a[i]) / d
            x = (d * d + r1 * r1 - r2 * r2) / (2 * d)
            h = math.sqrt(max(0.0, r1 * r1 - x * x))
            base = a[i] + u * x
            nrm = np.array([-u[1], u[0]])
            p1, p2 = base + nrm * h, base - nrm * h
            out[i] = p1 if np.hypot(*(p1 - b[i])) <= np.hypot(*(p2 - b[i])) else p2
        j[mid] = one_euro_2d(np.arange(len(out)) / fps, out, tu)


def one_euro_2d(t: np.ndarray, a: np.ndarray, tu: Tuning) -> np.ndarray:
    return np.stack([one_euro(t, a[:, 0], tu), one_euro(t, a[:, 1], tu)], axis=1)


def clean_poses(frames: list[PoseFrame], aspect: float = 1.0,
                tuning: Tuning | None = None) -> list[PoseFrame]:
    """Poses for drawing. `Point.visibility` in the result is opacity, 0..1."""
    tu = tuning or Tuning()
    keep = _same_body(frames, [f.cam or IDENTITY for f in frames], aspect)
    if len(keep) < 2:
        return [frames[i] for i in keep]
    t = np.array([frames[i].t for i in keep])
    cams = [frames[i].cam or IDENTITY for i in keep]
    fps = (len(t) - 1) / (t[-1] - t[0]) if t[-1] > t[0] else 15.0
    torso = float(np.median([_torso(frames[i], aspect) for i in keep]))
    names = list(POINTS) + [n for n in DETAIL if any(n in frames[i].points for i in keep)]
    raw: dict[str, np.ndarray] = {}
    conf: dict[str, np.ndarray] = {}
    for name in names:
        a = np.full((len(keep), 2), np.nan)
        c = np.zeros(len(keep))
        shown = False
        for row, i in enumerate(keep):
            p = frames[i].points.get(name)
            v = p.visibility if p else 0.0
            shown = v >= (tu.hide_below if shown else tu.show_from)
            if shown:
                wx, wy = _to_wall(cams[row], p.x, p.y)
                a[row] = (wx * aspect / torso, wy / torso)
                c[row] = v
        raw[name], conf[name] = a, c
    _unswap(raw)   # heels ride with nothing: few enough frames that a swap is rare
    joints: dict[str, np.ndarray] = {}
    alpha: dict[str, np.ndarray] = {}
    for name, a in raw.items():
        seen = ~np.isnan(a[:, 0])
        filled = np.stack([kalman_rts(t, a[:, k], conf[name], tu) for k in range(2)], axis=1)
        smooth = one_euro_2d(t, filled, tu)
        if tu.pin_holds and name in ENDS:
            smooth = _hold(t, smooth, seen, tu)
        joints[name], alpha[name] = smooth, _opacity(t, seen, tu)
    if tu.rigid_limbs:
        _rigid_limbs(joints, fps, tu)
    back = [np.linalg.inv(np.vstack([np.asarray(c, dtype=float), [0.0, 0.0, 1.0]]))[:2]
            for c in cams]
    out = []
    for row, ti in enumerate(t):
        pts = {}
        for name, a in joints.items():
            x, y = a[row]
            op = float(alpha[name][row])
            if np.isnan(x) or op <= 0.0:
                pts[name] = Point(0.0, 0.0, 0.0)
                continue
            px, py = _to_wall(back[row], float(x * torso / aspect), float(y * torso))
            pts[name] = Point(px, py, op)
        out.append(measure(PoseFrame(t=float(ti), points=pts, cam=cams[row])))
    return out
