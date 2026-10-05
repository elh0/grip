"""Brazilian jiu-jitsu rolls. Tangled bodies break tracking, so these rules stay modest."""

from __future__ import annotations

import math

from ..pose import PoseFrame
from . import Flag, Sport, dedupe

ELBOW_FLARE_RATIO = 1.1  # elbow-to-hip distance over torso length
FLAT_SPREAD = 0.06       # shoulders and hips this close in height reads as flat on the mat
SUSTAINED_FRAMES = 4


def rules(frames: list[PoseFrame]) -> list[Flag]:
    flags: list[Flag] = []
    flare = {"left": 0, "right": 0}
    flat = 0
    for pf in frames:
        for side in ("left", "right"):
            s, e, h = (pf.visible(f"{side}_{j}") for j in ("shoulder", "elbow", "hip"))
            if s and e and h:
                torso = math.dist((s.x, s.y), (h.x, h.y)) or 1e-6
                if math.dist((e.x, e.y), (h.x, h.y)) / torso > ELBOW_FLARE_RATIO:
                    flare[side] += 1
                    if flare[side] == SUSTAINED_FRAMES:
                        flags.append(Flag(pf.t, f"{side.title()} elbow",
                                          "flared away from the body for a while", "moderate"))
                    continue
            flare[side] = 0

        ls, rs, lh, rh = (pf.visible(n) for n in
                          ("left_shoulder", "right_shoulder", "left_hip", "right_hip"))
        if ls and rs and lh and rh:
            spread = abs((ls.y + rs.y) / 2 - (lh.y + rh.y) / 2)
            flat = flat + 1 if spread < FLAT_SPREAD else 0
            if flat == SUSTAINED_FRAMES:
                flags.append(Flag(pf.t, "Back", "flat on the mat; get onto a side", "major"))
        else:
            flat = 0
    return dedupe(flags)


SPORT = Sport(
    key="bjj",
    name="Jiu-jitsu",
    coach_brief=(
        "The athlete is rolling (sparring) in Brazilian jiu-jitsu. Two bodies may overlap; "
        "use the athlete's note to tell which person to review. Look at posture and base, "
        "frames and elbow-knee connection, hip movement (shrimping, bridging), grips, "
        "underhooks, head position, and whether they end up flat on their back."
    ),
    filming_tip="Film from the side of the mat with both bodies in frame the whole time.",
    rules=rules,
)
