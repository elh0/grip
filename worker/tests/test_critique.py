from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from coach_worker.critique import (
    SYSTEM,
    CoachContext,
    Critique,
    Keyframe,
    Note,
    build_brief,
    call_claude,
    fmt_time,
    offline_critique,
    tidy,
)
from coach_worker.sports import Flag, get_sport


def note(t, part="Left hip"):
    return Note(t_seconds=t, body_part=part, severity="moderate", observation="o", cue="c",
                drill="d")


def ctx(**kw):
    return CoachContext(sport=get_sport("climbing"), duration_s=20.0, **kw)


def test_fmt_time():
    assert fmt_time(42.7) == "0:42"
    assert fmt_time(125) == "2:05"
    assert fmt_time(-1) == "0:00"


def test_tidy_caps_at_three_sorts_and_clamps():
    c = tidy(Critique(summary=" s ", notes=[note(9), note(30), note(1), note(5)]), 20.0)
    assert [n.t_seconds for n in c.notes] == [1, 9, 20.0]
    assert c.summary == "s"


def test_brief_includes_profile_flags_and_angles():
    brief = build_brief(ctx(level="advanced", injuries="left shoulder", athlete_note="crux 0:04"),
                        [Flag(4.2, "Left arm", "bent")], ["- 0:04: left_elbow 95"])
    for text in ("Board climbing", "advanced", "left shoulder", "crux 0:04", "0:04 Left arm",
                 "left_elbow 95"):
        assert text in brief


def test_offline_critique_ranks_major_first():
    flags = [Flag(1, "Arm", "a", "minor"), Flag(2, "Foot", "b", "major"),
             Flag(3, "Hip", "c", "moderate"), Flag(4, "Head", "d", "minor")]
    c = offline_critique(ctx(), flags)
    assert {n.body_part for n in c.notes} == {"Foot", "Hip", "Arm"}
    assert offline_critique(ctx(), []).notes == []


def test_system_prompt_rules():
    assert "at most three" in SYSTEM.lower()
    assert "no emoji" in SYSTEM.lower()


class FakeMessages:
    def __init__(self, result):
        self.result = result
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return self.result


def test_call_claude_request_shape(tmp_path: Path):
    img = tmp_path / "k.jpg"
    Image.new("RGB", (8, 8)).save(img)
    parsed = Critique(summary="Hips drift out on the crux.", notes=[note(4.0), note(2.0)])
    messages = FakeMessages(SimpleNamespace(stop_reason="end_turn", parsed_output=parsed))
    client = SimpleNamespace(messages=messages)

    out = call_claude(client, model="claude-opus-5-5", effort="high", ctx=ctx(),
                      keyframes=[Keyframe(2.0, img), Keyframe(4.0, img)], flags=[], pose_lines=[])

    kw = messages.kwargs
    assert kw["model"] == "claude-opus-5-5"
    assert kw["output_format"] is Critique
    assert kw["system"] == SYSTEM
    assert kw["extra_body"] == {"fallbacks": "default"}
    assert kw["extra_headers"]["anthropic-beta"] == "server-side-fallback-2026-07-01"
    content = kw["messages"][0]["content"]
    assert [b["type"] for b in content] == ["text", "text", "image", "text", "image"]
    assert content[2]["source"]["media_type"] == "image/jpeg"
    assert [n.t_seconds for n in out.notes] == [2.0, 4.0]


def test_call_claude_refusal(tmp_path: Path):
    import pytest

    from coach_worker.critique import CritiqueError

    client = SimpleNamespace(messages=FakeMessages(
        SimpleNamespace(stop_reason="refusal", parsed_output=None)))
    with pytest.raises(CritiqueError):
        call_claude(client, model="m", effort="high", ctx=ctx(), keyframes=[], flags=[],
                    pose_lines=[])
