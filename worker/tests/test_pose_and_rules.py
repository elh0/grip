import math

import numpy as np
import pytest
from PIL import Image

from coach_worker.pose import POINTS, Point, PoseFrame, angle, draw_wireframe, measure, try_detector
from coach_worker.sports import Flag, dedupe, get_sport


def standing(t=0.0, elbow_bend=False, dx=0.0, ankle_dy=0.0, overhead=False) -> PoseFrame:
    p = {
        "nose": (0.5, 0.1), "left_shoulder": (0.45, 0.25), "right_shoulder": (0.55, 0.25),
        "left_elbow": (0.45, 0.4), "right_elbow": (0.55, 0.4),
        "left_wrist": (0.55, 0.4) if elbow_bend else (0.45, 0.55),
        "right_wrist": (0.55, 0.55),
        "left_hip": (0.46, 0.55), "right_hip": (0.54, 0.55),
        "left_knee": (0.46, 0.72), "right_knee": (0.54, 0.72),
        "left_ankle": (0.46, 0.9 - ankle_dy), "right_ankle": (0.54, 0.9),
        "left_foot": (0.47, 0.93), "right_foot": (0.55, 0.93),
    }
    if overhead:  # hanging from a hold: elbow and hand above the shoulder
        p["left_elbow"] = (0.45, 0.1)
        p["left_wrist"] = (0.55, 0.1) if elbow_bend else (0.45, -0.05)
    return measure(PoseFrame(t=t, points={k: Point(x + dx, y) for k, (x, y) in p.items()}))


def test_fifteen_points():
    assert len(POINTS) == 15


def test_angle():
    assert angle(Point(0, 0), Point(1, 0), Point(2, 0)) == pytest.approx(180)
    assert angle(Point(0, 0), Point(1, 0), Point(1, 1)) == pytest.approx(90)
    assert math.isnan(angle(Point(0, 0), Point(0, 0), Point(1, 1)))


def test_measure_and_com():
    pf = standing()
    assert pf.angles["left_elbow"] == pytest.approx(180)
    assert pf.angles["right_knee"] == pytest.approx(180)
    assert pf.com == pytest.approx((0.5, 0.45), abs=1e-6)


def test_low_visibility_points_are_ignored():
    pf = standing()
    pf.points["left_wrist"].visibility = 0.1
    pf.angles.clear()
    measure(pf)
    assert "left_elbow" not in pf.angles


def test_climbing_flags_bent_arm_when_hanging_still():
    frames = [standing(i * 0.2, elbow_bend=True, overhead=True) for i in range(6)]
    flags = [f for f in get_sport("climbing").rules(frames) if f.body_part == "Left arm"]
    assert len(flags) == 1, "one flag per hang, not one per frame"
    assert flags[0].t == 0.0 and "1.0s" in flags[0].message


def test_climbing_ignores_short_or_low_bent_arms():
    rules = get_sport("climbing").rules
    brief = [standing(i * 0.2, elbow_bend=True, overhead=True) for i in range(3)]
    assert not [f for f in rules(brief) if f.body_part == "Left arm"], "a moment mid-move is fine"
    pushing = [standing(i * 0.2, elbow_bend=True) for i in range(6)]
    assert not [f for f in rules(pushing) if f.body_part == "Left arm"], "hand below shoulder"


def test_climbing_flags_foot_cut():
    frames = [standing(0.0), standing(0.2, ankle_dy=0.2)]
    flags = get_sport("climbing").rules(frames)
    assert any(f.body_part == "Left foot" and f.severity == "major" for f in flags)


def test_bjj_flat_on_back_needs_sustained_frames():
    def flat(t):
        pf = standing(t)
        for k in ("left_shoulder", "right_shoulder"):
            pf.points[k].y = 0.55
        return measure(pf)

    rules = get_sport("bjj").rules
    assert not [f for f in rules([flat(i) for i in range(3)]) if f.body_part == "Back"]
    assert [f for f in rules([flat(i) for i in range(5)]) if f.body_part == "Back"]


def test_unknown_sport():
    with pytest.raises(ValueError):
        get_sport("golf")


def test_dedupe():
    flags = [Flag(0.0, "Hip", "x"), Flag(1.0, "Hip", "x"), Flag(3.5, "Hip", "x")]
    assert [f.t for f in dedupe(flags)] == [0.0, 3.5]


def test_draw_wireframe(tmp_path):
    src = tmp_path / "f.jpg"
    Image.new("RGB", (200, 200), "black").save(src)
    out = draw_wireframe(src, standing(), tmp_path / "o.jpg", trail=[(0.5, 0.4), (0.5, 0.45)])
    with Image.open(out) as im:
        px = np.asarray(im.convert("RGB")).reshape(-1, 3)
    assert ((px[:, 2] > 150) & (px[:, 0] < 150)).sum() > 100


def test_try_detector_without_model():
    assert try_detector("") is None
    assert try_detector("/nope.task") is None
