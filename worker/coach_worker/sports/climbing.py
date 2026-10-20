"""Bouldering, in a gym or on a board: short problems, often filmed handheld."""

from __future__ import annotations

import math

from ..pose import PoseFrame
from . import Flag, Sport, dedupe

BENT_ARM_DEG = 120.0     # elbow angle below this while static reads as a bent-arm rest
BENT_ARM_HOLD_S = 0.8    # only a hang this long counts; a moment of bent arm mid-move is normal
STATIC_COM_MOVE = 0.01   # centre-of-mass travel per frame (normalised) that counts as still
FOOT_CUT_JUMP = 0.08     # ankle travel per frame (normalised) while hands stay put


def _hanging(cur: PoseFrame, side: str) -> bool:
    """Hand above the shoulder: the arm is holding body weight, not pushing or mantling."""
    w, s = cur.visible(f"{side}_wrist"), cur.visible(f"{side}_shoulder")
    return bool(w and s and w.y < s.y)


def rules(frames: list[PoseFrame]) -> list[Flag]:
    flags: list[Flag] = []
    # per arm: (start time, smallest elbow angle) of the current still, bent hang
    runs: dict[str, tuple[float, float] | None] = {"left": None, "right": None}

    def close_run(side: str, end_t: float) -> None:
        run = runs[side]
        if run and end_t - run[0] >= BENT_ARM_HOLD_S:
            flags.append(Flag(run[0], f"{side.title()} arm",
                              f"hung bent at {run[1]:.0f}° for {end_t - run[0]:.1f}s; "
                              "straighten it to rest", "moderate"))
        runs[side] = None

    for prev, cur in zip(frames, frames[1:], strict=False):
        still = (
            prev.com is not None and cur.com is not None
            and math.dist(prev.com, cur.com) < STATIC_COM_MOVE
        )
        for side in ("left", "right"):
            elbow = cur.angles.get(f"{side}_elbow")
            if still and elbow is not None and elbow < BENT_ARM_DEG and _hanging(cur, side):
                run = runs[side]
                runs[side] = (run[0], min(run[1], elbow)) if run else (prev.t, elbow)
            else:
                close_run(side, cur.t)
            a0, a1 = prev.visible(f"{side}_ankle"), cur.visible(f"{side}_ankle")
            w0, w1 = prev.visible(f"{side}_wrist"), cur.visible(f"{side}_wrist")
            if a0 and a1 and w0 and w1:
                foot_move = math.dist((a0.x, a0.y), (a1.x, a1.y))
                hand_move = math.dist((w0.x, w0.y), (w1.x, w1.y))
                if foot_move > FOOT_CUT_JUMP and hand_move < STATIC_COM_MOVE * 2:
                    flags.append(Flag(cur.t, f"{side.title()} foot",
                                      "came off with hands static: possible foot cut", "major"))
    if frames:
        for side in ("left", "right"):
            close_run(side, frames[-1].t)
    return dedupe(flags)


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
