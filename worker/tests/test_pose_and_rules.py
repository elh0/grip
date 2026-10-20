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


FPS = 15


def clip(seconds: float, **kw) -> list[PoseFrame]:
    return [standing(i / FPS, **kw) for i in range(int(seconds * FPS))]


def climbing(frames):
    return get_sport("climbing").rules(frames)


def test_climbing_flags_bent_arm_when_hanging_still():
    flags = [f for f in climbing(clip(2.0, elbow_bend=True, overhead=True))
             if f.body_part == "Left arm"]
    assert len(flags) == 1, "one flag per hang, not one per frame"
    assert flags[0].t == 0.0 and "hung bent" in flags[0].message


def test_climbing_ignores_short_or_low_bent_arms():
    brief = clip(0.6, elbow_bend=True, overhead=True)
    assert not [f for f in climbing(brief) if f.body_part == "Left arm"], "a moment mid-move"
    pushing = clip(2.0, elbow_bend=True)
    assert not [f for f in climbing(pushing) if f.body_part == "Left arm"], "hand below shoulder"


def foot_drop(dy_left: float, dy_right: float = 0.0, over_s: float = 0.2, sag: float = 0.0
              ) -> list[PoseFrame]:
    """Still for a second, then the feet move by dy (down is positive) and stay there; the hips
    sag by `sag` as the weight comes onto the arms."""
    frames = clip(1.0)
    steps = int(over_s * FPS)
    for k in range(1, int(1.5 * FPS)):
        u = min(1.0, k / steps)
        pf = standing(1.0 + k / FPS, ankle_dy=-dy_left * u)
        pf.points["right_ankle"].y += dy_right * u
        pf.points["right_foot"].y += dy_right * u
        pf.points["left_foot"].y += dy_left * u
        for hip in ("left_hip", "right_hip"):
            pf.points[hip].y += sag * u
        frames.append(measure(pf))
    return frames


def test_climbing_flags_a_placed_foot_slipping():
    assert not climbing(foot_drop(0.2)), "fast alone could be the phone jolting"
    flags = climbing(foot_drop(0.2, sag=0.06))
    assert [f.body_part for f in flags] == ["Left foot"]
    assert flags[0].severity == "major" and 0.9 <= flags[0].t <= 1.1


def test_climbing_ignores_a_foot_moving_up():
    assert not climbing(foot_drop(-0.2, sag=0.06)), "stepping up onto the next hold is the climb"


def test_climbing_ignores_a_slow_step_down():
    assert not climbing(foot_drop(0.1, over_s=1.0, sag=0.06))


def test_climbing_flags_both_feet_cutting_loose():
    assert not climbing(foot_drop(0.2, 0.2)), "both feet landing at once is a planned move"
    flags = climbing(foot_drop(0.25, 0.25, sag=0.06))
    assert [f.body_part for f in flags] == ["Both feet"]


def test_climbing_ignores_feet_swapping_labels():
    """Side-on, the model can swap left and right for a moment: the feet didn't move."""
    frames = clip(2.0)
    for pf in frames[15:18]:
        for j in ("ankle", "foot", "knee"):
            pf.points[f"left_{j}"], pf.points[f"right_{j}"] = (pf.points[f"right_{j}"],
                                                             pf.points[f"left_{j}"])
    assert not climbing(frames)


def test_climbing_ignores_camera_panning():
    """A handheld phone pans: the whole picture moves, the climber doesn't."""
    frames = [standing(i / FPS, dx=0.3 * i / FPS) for i in range(30)]
    camera = [[[1.0, 0.0, -0.3 * i / FPS], [0.0, 1.0, 0.0]] for i in range(30)]
    flags = get_sport("climbing").rules(frames, aspect=1.0, camera=camera)
    assert not flags


def test_bjj_flat_on_back_needs_sustained_frames():
    def flat(t):
        pf = standing(t)
        for k in ("left_shoulder", "right_shoulder"):
            pf.points[k].y = 0.55
        return measure(pf)

    rules = get_sport("bjj").rules
    assert not [f for f in rules([flat(i * 0.2) for i in range(3)]) if f.body_part == "Back"]
    flags = [f for f in rules([flat(i * 0.2) for i in range(8)]) if f.body_part == "Back"]
    assert len(flags) == 1 and flags[0].t == 0.0


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
