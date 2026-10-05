from pathlib import Path

import pytest

from coach_worker import frames as fr


def test_probe(clip):
    meta = fr.probe(clip)
    assert meta.width == 320 and meta.height == 240
    assert meta.duration == pytest.approx(6.0, abs=0.1)


@pytest.mark.parametrize(
    "note,expected",
    [
        ("watch 0:12 to 0:18", (12.0, 18.0)),
        ("crux is 1:02-1:05.5 please", (62.0, 65.5)),
        ("I'm in the blue gi", None),
        ("0:20 to 0:10", None),
        (None, None),
    ],
)
def test_parse_window(note, expected):
    assert fr.parse_window(note) == expected


def test_sample_and_select(clip, tmp_path):
    frames = fr.sample_frames(clip, tmp_path, fps=4, width=160)
    assert 22 <= len(frames) <= 26
    assert frames[1].t == pytest.approx(0.25)
    fr.score_motion(frames)
    assert frames[0].motion == 0.0 and any(f.motion > 0 for f in frames)
    keys = fr.select_keyframes(frames, 8)
    assert len(keys) == 8
    assert [k.t for k in keys] == sorted(k.t for k in keys)


def _fake(n: int) -> list[fr.Frame]:
    return [fr.Frame(t=i * 0.5, path=Path(f"{i}.jpg"), motion=float(i % 3)) for i in range(n)]


def test_select_prefers_motion_within_each_slice():
    keys = fr.select_keyframes(_fake(12), 4)
    assert all(k.motion == 2.0 for k in keys)


def test_select_window_gets_half_the_budget():
    keys = fr.select_keyframes(_fake(40), 8, window=(5.0, 8.0))
    inside = [k for k in keys if 5.0 <= k.t <= 8.0]
    assert len(inside) == 4 and len(keys) == 8


def test_select_edges():
    assert fr.select_keyframes([], 8) == []
    assert len(fr.select_keyframes(_fake(3), 8)) == 3
