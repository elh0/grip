"""A log of how the body moved, for tuning the tracker and for later features.

Not part of a review: nothing here reaches the climber or the coach until it's been checked
against real climbs. Built from the steady drawing poses (`steady.clean_poses`), so a hand
that rests on a hold is one fixed spot on the wall and its rest is easy to time.

- holds: each spell a hand or foot rests in one place (wall position, start, end, seconds)
- frames, about 10 a second: head relative to the hips and to the hands (torso lengths,
  x right, y down), and hip distance from the wall (estimate, metres)

Hip distance from the wall comes from the model's own 3D guess: the hands and feet resting
on holds mark the wall, and the hips' depth is measured from them. One phone can't see depth,
so it's an estimate (`est`), good for "hips came in" rather than centimetres.
"""

from __future__ import annotations

import math

import numpy as np

from .motion import _to_wall
from .pose import PoseFrame

CONTACTS = ("left_wrist", "right_wrist", "left_ankle", "right_ankle")
MIN_REST_S = 0.25


def _wall(pf: PoseFrame, name: str) -> tuple[float, float] | None:
    q = pf.points.get(name)
    if not q or q.visibility < 0.5:
        return None
    return _to_wall(pf.cam or [[1, 0, 0], [0, 1, 0]], q.x, q.y)


def _rests(drawn: list[PoseFrame]) -> dict[str, list[tuple[int, int]]]:
    """Index runs where each contact sits still on the wall (pinned by the drawing)."""
    out: dict[str, list[tuple[int, int]]] = {}
    for n in CONTACTS:
        w = [_wall(pf, n) for pf in drawn]
        runs, start = [], None
        for i in range(1, len(w) + 1):
            same = (i < len(w) and w[i] is not None and w[i - 1] is not None
                    and math.dist(w[i], w[i - 1]) < 1e-6)
            if same and start is None:
                start = i - 1
            elif not same and start is not None:
                if drawn[i - 1].t - drawn[start].t >= MIN_REST_S:
                    runs.append((start, i - 1))
                start = None
        out[n] = runs
    return out


def tracking_log(raw: list[PoseFrame], drawn: list[PoseFrame], aspect: float,
                 every_s: float = 0.1) -> dict:
    if not drawn:
        return {"holds": [], "frames": []}
    rests = _rests(drawn)
    holds = []
    for n, runs in rests.items():
        for a, b in runs:
            x, y = _wall(drawn[a], n)
            holds.append({"limb": n.replace("_wrist", "_hand").replace("_ankle", "_foot"),
                          "t_start": round(drawn[a].t, 2), "t_end": round(drawn[b].t, 2),
                          "seconds": round(drawn[b].t - drawn[a].t, 2),
                          "wall": [round(float(x), 4), round(float(y), 4)]})
    holds.sort(key=lambda h: h["t_start"])
    resting = {n: np.zeros(len(drawn), bool) for n in CONTACTS}
    for n, runs in rests.items():
        for a, b in runs:
            resting[n][a:b + 1] = True
    world = {round(f.t, 3): f.world for f in raw if f.world}
    frames, next_t = [], drawn[0].t
    for i, pf in enumerate(drawn):
        if pf.t + 1e-6 < next_t:
            continue
        next_t = pf.t + every_s
        row: dict = {"t": round(pf.t, 2)}
        lh, rh, ls, rs = (pf.points.get(n) for n in
                          ("left_hip", "right_hip", "left_shoulder", "right_shoulder"))
        nose = pf.points.get("nose")
        ok = all(p and p.visibility >= 0.5 for p in (lh, rh, ls, rs))
        if ok and nose and nose.visibility >= 0.5:
            hx, hy = (lh.x + rh.x) / 2, (lh.y + rh.y) / 2
            torso = math.hypot(((ls.x + rs.x) / 2 - hx) * aspect, (ls.y + rs.y) / 2 - hy) or 1.0
            row["head_from_hips"] = [round(float((nose.x - hx) * aspect / torso), 2),
                                     round(float((nose.y - hy) / torso), 2)]
            hands = [pf.points.get(n) for n in ("left_wrist", "right_wrist")]
            hands = [h for h in hands if h and h.visibility >= 0.5]
            if hands:
                mx = sum(h.x for h in hands) / len(hands)
                my = sum(h.y for h in hands) / len(hands)
                row["head_from_hands"] = [round(float((nose.x - mx) * aspect / torso), 2),
                                          round(float((nose.y - my) / torso), 2)]
        w = world.get(round(pf.t, 3))
        on = [n for n in CONTACTS if resting[n][i]]
        if w and on and all(n in w for n in on):
            wall_z = float(np.median([w[n][2] for n in on]))
            hip_z = (w["left_hip"][2] + w["right_hip"][2]) / 2
            row["hip_off_wall_m"] = round(max(0.0, wall_z - hip_z), 2)
            row["est"] = ["hip_off_wall_m"]
        frames.append(row)
    return {"holds": holds, "frames": frames}
