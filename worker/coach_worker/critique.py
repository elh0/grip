"""The coach: system prompt, output schema and the Claude call."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .sports import Flag, Sport

MAX_NOTES = 3

SYSTEM = """\
You are grip, a coach who has rewatched the athlete's tape. You review one filmed session \
(a board climb or a jiu-jitsu roll) from a handful of timestamped still frames, optional \
pose hints, and what the athlete has told you about themselves.

Give at most three notes. Fewer is better when fewer things matter. Pick the faults that \
cost the athlete the most, not every fault you can see. Each note is tied to one moment \
(use the timestamp of the frame that shows it), one body part, and gives:
- observation: what the body did, in one short sentence
- cue: what to do instead, in the words a coach would shout from the mat or the floor
- drill: one specific drill or exercise for the next session

Voice: short, specific, dry, on the athlete's side. Speak the sport (beta, flag, \
drop-knee, heel hook, underhook, base, frames, shrimp) without explaining it. No hype, \
no emoji, no scores or ratings, no "unlock your potential". Never invent detail you \
cannot see in the frames; if the footage cannot show something (for example hip-to-wall \
distance from directly behind), say so in the summary and suggest a better angle.

Pose hints come from an automatic tracker. Treat them as hints that may be wrong, \
especially in jiu-jitsu where two bodies overlap. Respect injuries: never cue a \
movement that loads an injury the athlete has named.

The summary is one sentence the athlete reads first.\
"""


class Note(BaseModel):
    t_seconds: float = Field(description="Timestamp of the frame that shows the fault")
    body_part: str = Field(description="e.g. 'Left hip', 'Right foot', 'Head'")
    severity: Literal["minor", "moderate", "major"]
    observation: str
    cue: str
    drill: str


class Critique(BaseModel):
    summary: str
    notes: list[Note] = Field(description="At most three, most important first")


@dataclass
class CoachContext:
    sport: Sport
    duration_s: float
    level: str | None = None
    goals: str | None = None
    injuries: str | None = None
    athlete_note: str | None = None


@dataclass
class Keyframe:
    t: float
    path: Path


def fmt_time(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 60)}:{int(t % 60):02d}"


def build_brief(ctx: CoachContext, flags: list[Flag], pose_lines: list[str]) -> str:
    lines = [
        f"Sport: {ctx.sport.name}. {ctx.sport.coach_brief}",
        f"Clip length: {fmt_time(ctx.duration_s)}.",
    ]
    if ctx.level:
        lines.append(f"Level: {ctx.level}.")
    if ctx.goals:
        lines.append(f"Goals: {ctx.goals}")
    if ctx.injuries:
        lines.append(f"Injuries to respect: {ctx.injuries}")
    if ctx.athlete_note:
        lines.append(f"Athlete's note: {ctx.athlete_note}")
    if flags:
        lines.append("Tracker flags (hints, may be wrong):")
        lines += [f"- {fmt_time(f.t)} {f.body_part}: {f.message}" for f in flags]
    if pose_lines:
        lines.append("Joint angles at each frame (degrees, 180 = straight):")
        lines += pose_lines
    lines.append("Review the frames below and return your notes.")
    return "\n".join(lines)


def build_content(brief: str, keyframes: list[Keyframe]) -> list[dict]:
    content: list[dict] = [{"type": "text", "text": brief}]
    for i, kf in enumerate(keyframes, 1):
        content.append({"type": "text", "text": f"Frame {i} at {fmt_time(kf.t)} (t={kf.t:.2f}s)"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.b64encode(kf.path.read_bytes()).decode("ascii"),
            },
        })
    return content


def tidy(critique: Critique, duration_s: float) -> Critique:
    """Enforce the product rules whatever the model returns."""
    notes = sorted(critique.notes[:MAX_NOTES], key=lambda n: n.t_seconds)
    for n in notes:
        n.t_seconds = round(min(max(0.0, n.t_seconds), max(0.0, duration_s)), 2)
    return Critique(summary=critique.summary.strip(), notes=notes)


def call_claude(client, *, model: str, effort: str, ctx: CoachContext,
                keyframes: list[Keyframe], flags: list[Flag], pose_lines: list[str]) -> Critique:
    """One structured-output request. `client` is an anthropic.Anthropic()."""
    response = client.messages.parse(
        model=model,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user",
                   "content": build_content(build_brief(ctx, flags, pose_lines), keyframes)}],
        output_format=Critique,
        output_config={"effort": effort},
        # Re-run a declined request on Anthropic's recommended fallback model.
        extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
        extra_body={"fallbacks": "default"},
    )
    if response.stop_reason == "refusal":
        raise CritiqueError("the model declined to review this clip")
    if response.parsed_output is None:
        raise CritiqueError(f"no structured output (stop_reason={response.stop_reason})")
    return tidy(response.parsed_output, ctx.duration_s)


def offline_critique(ctx: CoachContext, flags: list[Flag]) -> Critique:
    """No API key: turn the strongest tracker flags into notes so the pipeline still runs."""
    rank = {"major": 0, "moderate": 1, "minor": 2}
    top = sorted(flags, key=lambda f: (rank.get(f.severity, 3), f.t))[:MAX_NOTES]
    notes = [
        Note(t_seconds=f.t, body_part=f.body_part, severity=f.severity,  # type: ignore[arg-type]
             observation=f.message, cue="Check this moment on the replay.",
             drill="Repeat the move slowly, filmed from the same spot.")
        for f in top
    ]
    summary = ("Offline review: tracker flags only, no coach notes."
               if notes else "Offline review: nothing flagged by the tracker.")
    return tidy(Critique(summary=summary, notes=notes), ctx.duration_s)


class CritiqueError(RuntimeError):
    pass
