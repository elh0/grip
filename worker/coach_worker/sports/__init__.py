"""Sport rules: cheap pose heuristics that become hints for the coach, never verdicts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Flag:
    t: float
    body_part: str
    message: str
    severity: str = "moderate"  # minor | moderate | major


@dataclass
class Sport:
    key: str
    name: str
    coach_brief: str
    filming_tip: str
    # rules(poses, aspect=width/height, camera=motion.camera_motion output, one per pose)
    rules: Callable[..., list[Flag]]


def get_sport(key: str) -> Sport:
    from . import bjj, climbing

    sports = {climbing.SPORT.key: climbing.SPORT, bjj.SPORT.key: bjj.SPORT}
    try:
        return sports[key]
    except KeyError:
        raise ValueError(f"unknown sport {key!r}; expected one of {sorted(sports)}") from None


def dedupe(flags: list[Flag], min_gap_s: float = 2.0) -> list[Flag]:
    """Keep one flag per message per `min_gap_s` window."""
    kept: list[Flag] = []
    last: dict[str, float] = {}
    for f in sorted(flags, key=lambda f: f.t):
        key = f"{f.body_part}:{f.message}"
        if key in last and f.t - last[key] < min_gap_s:
            continue
        last[key] = f.t
        kept.append(f)
    return kept
