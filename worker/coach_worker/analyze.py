"""The seam: analyze(video, ctx) -> Analysis.

Sample frames, score motion, pick keyframes (dense in the athlete's window if given),
run optional pose, apply sport rules, then ask the coach.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from . import frames as fr
from .config import Settings
from .critique import (
    CoachContext,
    Critique,
    Keyframe,
    call_claude,
    fmt_time,
    offline_critique,
)
from .pose import PoseDetector, PoseFrame, draw_wireframe, try_detector
from .sports import Flag

WINDOW_FPS_MULTIPLIER = 3


@dataclass
class Analysis:
    critique: Critique
    keyframes: list[Keyframe]            # what the coach saw (with wireframes when pose ran)
    flags: list[Flag] = field(default_factory=list)
    pose_frames: int = 0
    offline: bool = False

    def frame_for(self, t: float) -> Keyframe | None:
        """The keyframe nearest a note's timestamp."""
        return min(self.keyframes, key=lambda k: abs(k.t - t), default=None)


def analyze(video: Path, ctx: CoachContext, settings: Settings, work_dir: Path,
            client=None, detector: PoseDetector | None = None) -> Analysis:
    work_dir.mkdir(parents=True, exist_ok=True)
    window = fr.parse_window(ctx.athlete_note)

    sampled = fr.sample_frames(video, work_dir / "sampled", settings.sample_fps,
                               settings.keyframe_width)
    if window:
        start, end = window[0], min(window[1], ctx.duration_s or window[1])
        dense = fr.sample_frames(video, work_dir / "window",
                                 settings.sample_fps * WINDOW_FPS_MULTIPLIER,
                                 settings.keyframe_width, start=start, end=end, prefix="w")
        sampled = sorted([f for f in sampled if not start <= f.t <= end] + dense,
                         key=lambda f: f.t)
    fr.score_motion(sampled)

    own_detector = detector is None
    detector = detector or try_detector(settings.pose_model_path)
    poses: list[PoseFrame] = []
    try:
        if detector:
            poses = [p for f in sampled if (p := detector.detect(f.path, f.t))]
    finally:
        if own_detector and detector:
            detector.close()

    flags = ctx.sport.rules(poses) if poses else []
    chosen = fr.select_keyframes(sampled, settings.max_keyframes, window)

    keyframes, pose_lines = _overlay(chosen, poses, work_dir / "keyframes")

    if settings.offline or client is None:
        critique = offline_critique(ctx, flags)
        offline = True
    else:
        critique = call_claude(client, model=settings.model, effort=settings.effort, ctx=ctx,
                               keyframes=keyframes, flags=flags, pose_lines=pose_lines)
        offline = False
    return Analysis(critique=critique, keyframes=keyframes, flags=flags,
                    pose_frames=len(poses), offline=offline)


def _overlay(chosen: list[fr.Frame], poses: list[PoseFrame], out_dir: Path
             ) -> tuple[list[Keyframe], list[str]]:
    """Draw the wireframe on each keyframe that has a pose near it."""
    by_t = {round(p.t, 3): p for p in poses}
    trail = [p.com for p in poses if p.com]
    keyframes: list[Keyframe] = []
    lines: list[str] = []
    for i, f in enumerate(chosen, 1):
        pf = by_t.get(round(f.t, 3))
        if pf:
            path = draw_wireframe(f.path, pf, out_dir / f"k{i:02d}.jpg",
                                  trail=[c for c in trail if c] if trail else None)
            angles = ", ".join(f"{k} {v:.0f}" for k, v in pf.angles.items() if not math.isnan(v))
            if angles:
                lines.append(f"- {fmt_time(f.t)}: {angles}")
        else:
            path = f.path
        keyframes.append(Keyframe(t=f.t, path=path))
    return keyframes, lines
