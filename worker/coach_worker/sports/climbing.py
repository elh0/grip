"""Board climbing (Moon, Kilter, Tension): short, repeatable, filmed from a fixed angle."""

from __future__ import annotations

import math

from ..pose import PoseFrame
from . import Flag, Sport, dedupe

BENT_ARM_DEG = 120.0     # elbow angle below this while static reads as a bent-arm rest
STATIC_COM_MOVE = 0.01   # centre-of-mass travel per frame (normalised) that counts as still
FOOT_CUT_JUMP = 0.08     # ankle travel per frame (normalised) while hands stay put


def rules(frames: list[PoseFrame]) -> list[Flag]:
    flags: list[Flag] = []
    for prev, cur in zip(frames, frames[1:], strict=False):
        still = (
            prev.com is not None and cur.com is not None
            and math.dist(prev.com, cur.com) < STATIC_COM_MOVE
        )
        for side in ("left", "right"):
            elbow = cur.angles.get(f"{side}_elbow")
            if still and elbow is not None and elbow < BENT_ARM_DEG:
                flags.append(Flag(cur.t, f"{side.title()} arm",
                                  f"bent to {elbow:.0f}° while static; hang straight to rest",
                                  "moderate"))
            a0, a1 = prev.visible(f"{side}_ankle"), cur.visible(f"{side}_ankle")
            w0, w1 = prev.visible(f"{side}_wrist"), cur.visible(f"{side}_wrist")
            if a0 and a1 and w0 and w1:
                foot_move = math.dist((a0.x, a0.y), (a1.x, a1.y))
                hand_move = math.dist((w0.x, w0.y), (w1.x, w1.y))
                if foot_move > FOOT_CUT_JUMP and hand_move < STATIC_COM_MOVE * 2:
                    flags.append(Flag(cur.t, f"{side.title()} foot",
                                      "came off with hands static: possible foot cut", "major"))
    return dedupe(flags)


SPORT = Sport(
    key="climbing",
    name="Board climbing",
    coach_brief=(
        "The athlete is climbing on a training board (Moon, Kilter or Tension style). "
        "Look at hip position relative to the wall, straight arms on static moves, "
        "quiet and precise feet, flagging, drop-knees, body tension through the core, "
        "and timing of the move to the next hold."
    ),
    filming_tip="Film side-on or at 45°; from directly behind, hip-to-wall distance is hidden.",
    rules=rules,
)
