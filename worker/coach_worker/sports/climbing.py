"""Bouldering, in a gym or on a board: short problems, often filmed handheld.

The rules read a cleaned track (see motion.py): one climber, smoothed joints, camera panning
taken out, distances in torso lengths and speeds per second. Tuned on real BlocFit clips
(17 Oct 2026). They are hints for the coach, so they stay quiet unless the pattern is clear.
"""

from __future__ import annotations

import warnings

import numpy as np

from ..motion import Track, build_track
from ..pose import PoseFrame
from . import Flag, Sport, dedupe

# Still: speeds in torso lengths per second.
HOLD_SPEED = 0.6          # a hand slower than this is on a hold
PLANTED_SPEED = 0.5       # a foot slower than this is standing on something
STILL_COM_SPEED = 0.35    # the body slower than this is resting, not moving

# Bent-arm hang
BENT_ARM_DEG = 110.0      # elbow angle below this on a still hang
BENT_ARM_HOLD_S = 1.0     # a moment of bent arm mid-move is normal; a long one is a rest done wrong
GAP_S = 0.3               # a check failing for this long or less doesn't end a hang
FORESHORTEN = 0.65        # an arm drawn shorter than this share of its usual length points at the
                          # camera, and its angle can't be trusted

# Feet
FOOT_MOVE_SPEED = 1.2     # a foot faster than this is moving
PLANTED_BEFORE_S = 0.4    # a slip starts from a foot that was standing still this long
SLIP_DROP = 0.35          # a slip drops at least this far, mostly downwards
SLIP_PEAK_SPEED = 1.5     # and fast enough to be more than a careful step down
SLIP_SAG = 0.1            # with the hips sagging this far as the weight comes off the foot...
SAG_AFTER_S = 0.5         # the sag can land just after the foot goes
SLIP_KNEE_OPEN = 80.0     # ...or the leg shooting straight as the foot skates away (sat low,
                          # the hips can't sag much). Speed alone isn't enough: a phone jolt
                          # looks fast too.
SLIP_DOWNWARD = 0.5       # and heading down, at least 30° below level (a skate slides down and out)
CUT_TRAVEL = 0.5          # both feet travelling at least this far together is a foot cut
CUT_SYNC_S = 0.25         # starting within this of each other
CUT_MAX_RISE = 0.3        # and neither foot going mostly upwards
DANGLE_S = 0.5            # feet still moving this long after a cut: they never found a hold
FOOT_EVENT_S = 1.0        # foot flags closer than this are the same moment
MIN_TORSO = 0.13          # torso under this share of the frame height (the climber under about
                          # 40% of it): too far away to read feet and elbows from

MAX_FLAGS = 6             # the coach gets the clearest few, not a list

SIDES = ("left", "right")


def _nanmedian(a: np.ndarray) -> float:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return float(np.nanmedian(a)) if a.size else float("nan")


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """(start, end) index pairs of True runs, end inclusive."""
    runs, start = [], None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        elif not m and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(mask) - 1))
    return runs


def _bridge(mask: np.ndarray, gap: int) -> np.ndarray:
    """Fill False gaps of at most `gap` samples between True runs: a blip isn't the hang ending."""
    out = mask.copy()
    runs = _runs(mask)
    for (_, b0), (a1, _) in zip(runs, runs[1:], strict=False):
        if a1 - b0 - 1 <= gap:
            out[b0 + 1:a1] = True
    return out


def _elbow(tr: Track, side: str) -> tuple[np.ndarray, np.ndarray]:
    """Elbow angle in degrees, and whether the arm is drawn at a length we can trust."""
    s, e, w = (tr.joints[f"{side}_{j}"] for j in ("shoulder", "elbow", "wrist"))
    ang = _angle(s, e, w)
    n1, n2 = np.hypot(*(s - e).T), np.hypot(*(w - e).T)
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        ok = (n1 >= FORESHORTEN * np.nanpercentile(n1, 90)) & \
                 (n2 >= FORESHORTEN * np.nanpercentile(n2, 90))
    return ang, ok


def _knee(tr: Track, side: str) -> np.ndarray:
    return _angle(*(tr.joints[f"{side}_{j}"] for j in ("hip", "knee", "ankle")))


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Angle at b in degrees, per frame."""
    v1, v2 = a - b, c - b
    with np.errstate(all="ignore"):
        cos = (v1 * v2).sum(axis=1) / (np.hypot(*v1.T) * np.hypot(*v2.T))
        return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def _hands_on(tr: Track, a: int, b: int) -> bool:
    """Every hand we can see is still on a hold from a to b, and we can see at least one."""
    seen = False
    for side in SIDES:
        sp = tr.speed(f"{side}_wrist")[a:b + 1]
        if np.isnan(sp).all():
            continue
        seen = True
        if _nanmedian(sp) >= HOLD_SPEED:
            return False
    return seen


def _bent_arms(tr: Track) -> list[Flag]:
    flags = []
    com = tr.mid("left_hip", "right_hip") * (2 / 3) + tr.mid("left_shoulder", "right_shoulder") / 3
    com_speed = np.hypot(*np.gradient(com, axis=0).T) / np.gradient(tr.t)
    for side in SIDES:
        ang, ok = _elbow(tr, side)
        wrist, shoulder = tr.joints[f"{side}_wrist"], tr.joints[f"{side}_shoulder"]
        with np.errstate(invalid="ignore"):
            hang = (ang < BENT_ARM_DEG) & ok & (wrist[:, 1] < shoulder[:, 1]) \
                & (com_speed < STILL_COM_SPEED) & (tr.speed(f"{side}_wrist") < HOLD_SPEED)
        for a, b in _runs(_bridge(hang, int(round(GAP_S * tr.fps)))):
            held = tr.t[b] - tr.t[a]
            if held >= BENT_ARM_HOLD_S:
                flags.append(Flag(float(tr.t[a]), f"{side.title()} arm",
                                  f"hung bent at {np.nanmin(ang[a:b + 1]):.0f}° for {held:.1f}s; "
                                  "straighten it to rest", "moderate"))
    return flags


def _shift(tr: Track, name: str, a: int, b: int) -> np.ndarray:
    """How far a joint got from just before a move to just after it, against the hands.

    The run above the speed threshold misses the slow start and finish, so it is padded. The
    rules only call this while the hands hold on, so any drift the hands show is the camera
    estimate slipping, and it is taken off.
    """
    pad = max(1, int(round(0.1 * tr.fps)))
    i, j = max(0, a - pad), min(len(tr.t) - 1, b + pad)
    hands = [tr.joints[f"{s}_wrist"][j] - tr.joints[f"{s}_wrist"][i] for s in SIDES]
    hands = [h for h in hands if not np.isnan(h).any()]
    drift = np.mean(hands, axis=0) if hands else np.zeros(2)
    return tr.joints[name][j] - tr.joints[name][i] - drift


def _sag(tr: Track, a: int, b: int) -> float:
    """How far the hips dropped from just before a move to just after it."""
    hips = tr.mid("left_hip", "right_hip")[:, 1]
    after = b + 1 + int(round(SAG_AFTER_S * tr.fps))
    window = hips[a:after]
    if np.isnan(window).all() or np.isnan(hips[max(0, a - 1)]):
        return 0.0
    return float(np.nanmax(window) - hips[max(0, a - 1)])


def _dangling(tr: Track, b: int) -> bool:
    """Neither foot settles in the half second after a move."""
    n = int(round(DANGLE_S * tr.fps))
    for side in SIDES:
        sp = tr.speed(f"{side}_ankle")[b + 1:b + 1 + n]
        if len(sp) < n or (not np.isnan(sp).all() and _nanmedian(sp) < PLANTED_SPEED):
            return False
    return True


def _foot_moves(tr: Track, side: str) -> list[tuple[int, int]]:
    sp = tr.speed(f"{side}_ankle")
    with np.errstate(invalid="ignore"):
        return _runs(sp > FOOT_MOVE_SPEED)


def _planted_before(tr: Track, side: str, i: int) -> bool:
    """The foot stood still for a while before the move (a slide speeds up, so skip its start)."""
    n = max(2, int(round(PLANTED_BEFORE_S * tr.fps)))
    lead = max(1, int(round(0.15 * tr.fps)))
    sp = tr.speed(f"{side}_ankle")[max(0, i - lead - n):max(0, i - lead)]
    return len(sp) >= n and not np.isnan(sp).any() and _nanmedian(sp) < PLANTED_SPEED


def _feet(tr: Track) -> list[Flag]:
    flags = []
    moves = {side: _foot_moves(tr, side) for side in SIDES}
    used: set[tuple[str, int]] = set()
    # Foot cut: both feet leave together while the hands hang on.
    for a0, b0 in moves["left"]:
        for a1, b1 in moves["right"]:
            if abs(tr.t[a0] - tr.t[a1]) > CUT_SYNC_S:
                continue
            a, b = min(a0, a1), max(b0, b1)
            shifts = [_shift(tr, f"{s}_ankle", st, e)
                      for s, st, e in (("left", a0, b0), ("right", a1, b1))]
            travel = [float(np.hypot(*d)) for d in shifts]
            # feet going up together is stepping onto the wall or a hop, not a cut
            upward = any(d[1] < -CUT_MAX_RISE * t for d, t in zip(shifts, travel, strict=True))
            if min(travel) < CUT_TRAVEL or upward or not _hands_on(tr, a, b):
                continue
            # a cut leaves the body hanging: the hips sag or the feet swing on without landing,
            # where a planned double foot move lands both feet straight away
            if _sag(tr, a, b) < SLIP_SAG and not _dangling(tr, b):
                continue
            flags.append(Flag(float(tr.t[a]), "Both feet",
                              "both feet came off while the hands held on: a foot cut; "
                              "keep pulling with the toes", "major"))
            used.update({("left", a0), ("right", a1)})
    # Slip: one placed foot drops fast while the hands and the other foot stay put.
    for side in SIDES:
        other = "right" if side == "left" else "left"
        for a, b in moves[side]:
            if (side, a) in used or not _planted_before(tr, side, a):
                continue
            d = _shift(tr, f"{side}_ankle", a, b)
            drop = float(np.hypot(*d))
            if not (drop >= SLIP_DROP and d[1] >= SLIP_DOWNWARD * drop):
                continue
            peak = np.nanmax(tr.speed(f"{side}_ankle")[a:b + 1])
            after = b + 1 + int(round(SAG_AFTER_S * tr.fps))
            sag = _sag(tr, a, b)
            knee = _knee(tr, side)
            opened = np.nanmax(knee[a:after]) - knee[max(0, a - 1)] if len(knee) else 0.0
            clear = sag >= SLIP_SAG or opened >= SLIP_KNEE_OPEN
            if peak < SLIP_PEAK_SPEED or not clear:
                continue
            if not _hands_on(tr, a, b):
                continue
            osp = tr.speed(f"{other}_ankle")[a:b + 1]
            if not np.isnan(osp).all() and _nanmedian(osp) >= PLANTED_SPEED:
                continue
            flags.append(Flag(float(tr.t[a]), f"{side.title()} foot",
                              "a placed foot came off and dropped; watch it onto the hold "
                              "until it's weighted", "major"))
    return flags


def _one_per_foot_event(flags: list[Flag]) -> list[Flag]:
    """A slip that turns into both feet off is one moment, not two flags."""
    kept: list[Flag] = []
    for f in sorted(flags, key=lambda f: f.t):
        if not kept or f.t - kept[-1].t > FOOT_EVENT_S:
            kept.append(f)
    return kept


def rules(frames: list[PoseFrame], aspect: float = 1.0,
          camera: list | None = None) -> list[Flag]:
    tr = build_track(frames, aspect, camera)
    if tr is None or tr.fps < 4 or tr.torso < MIN_TORSO:
        return []
    flags = dedupe(_one_per_foot_event(_feet(tr)) + _bent_arms(tr))
    rank = {"major": 0, "moderate": 1, "minor": 2}
    keep = sorted(flags, key=lambda f: (rank.get(f.severity, 3), f.t))[:MAX_FLAGS]
    return sorted(keep, key=lambda f: f.t)


SPORT = Sport(
    key="climbing",
    name="Bouldering",
    coach_brief=(
        "The athlete is bouldering, usually on a gym problem, sometimes a training board. "
        "The phone may be handheld and panning to follow them. "
        "Look at hip position relative to the wall, straight arms on static moves, "
        "quiet and precise feet, flagging, drop-knees, body tension through the core, "
        "and timing of the move to the next hold."
    ),
    filming_tip="Film side-on or at 45°; from directly behind, hip-to-wall distance is hidden.",
    rules=rules,
)
