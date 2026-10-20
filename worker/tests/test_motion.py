"""The cleaned track: one body, wall coordinates, torso units, left and right kept apart."""

import numpy as np
import pytest
from PIL import Image, ImageFilter

from coach_worker.motion import build_track, camera_motion, clean_poses
from coach_worker.pose import Point, PoseFrame, measure


def body(t: float, dx: float = 0.0, scale: float = 1.0, ankle_x=(0.46, 0.54)) -> PoseFrame:
    p = {
        "nose": (0.5, 0.1), "left_shoulder": (0.45, 0.25), "right_shoulder": (0.55, 0.25),
        "left_elbow": (0.45, 0.4), "right_elbow": (0.55, 0.4),
        "left_wrist": (0.45, 0.55), "right_wrist": (0.55, 0.55),
        "left_hip": (0.46, 0.55), "right_hip": (0.54, 0.55),
        "left_knee": (0.46, 0.72), "right_knee": (0.54, 0.72),
        "left_ankle": (ankle_x[0], 0.9), "right_ankle": (ankle_x[1], 0.9),
        "left_foot": (ankle_x[0], 0.93), "right_foot": (ankle_x[1], 0.93),
    }
    pts = {k: Point(0.5 + (x - 0.5) * scale + dx, 0.5 + (y - 0.5) * scale)
           for k, (x, y) in p.items()}
    return measure(PoseFrame(t=t, points=pts))


def test_units_are_torso_lengths_and_aspect_is_applied():
    tr = build_track([body(i / 15) for i in range(10)], aspect=1.0)
    hips = tr.mid("left_hip", "right_hip")[5]
    shoulders = tr.mid("left_shoulder", "right_shoulder")[5]
    assert np.hypot(*(hips - shoulders)) == pytest.approx(1.0)
    wide = build_track([body(i / 15) for i in range(10)], aspect=16 / 9)
    assert wide.torso == pytest.approx(0.3)  # an upright torso doesn't change with aspect


def test_drops_frames_from_someone_else():
    frames = [body(i / 15) for i in range(20)]
    frames[10] = body(10 / 15, dx=0.4, scale=0.5)  # a smaller person across the room
    tr = build_track(frames)
    assert len(tr.t) == 19 and 10 / 15 not in tr.t


def test_left_and_right_feet_are_unswapped():
    frames = [body(i / 15, ankle_x=(0.3, 0.7)) for i in range(20)]
    for i in (8, 9, 10):
        frames[i] = body(i / 15, ankle_x=(0.7, 0.3))  # the model swapped the labels
    tr = build_track(frames)
    left_x = tr.joints["left_ankle"][:, 0]
    assert np.nanmax(left_x) - np.nanmin(left_x) < 0.05


def test_camera_motion_follows_a_pan(tmp_path):
    pytest.importorskip("cv2")  # comes with the optional pose install
    rng = np.random.default_rng(0)
    wall = (rng.random((400, 800)) * 255).astype(np.uint8)
    wall = np.asarray(Image.fromarray(wall).filter(ImageFilter.GaussianBlur(1)))
    paths = []
    for i in range(5):  # the phone pans right 10 px a frame, so the wall slides left
        p = tmp_path / f"{i}.png"
        Image.fromarray(wall[:, 10 * i:10 * i + 320]).save(p)
        paths.append(p)
    cam = camera_motion(paths)
    assert len(cam) == 5
    # frame 4's left edge is 40 px right of frame 0's: x maps to x + 40/320 in frame 0
    assert cam[4][0][2] == pytest.approx(40 / 320, abs=0.01)
    assert cam[4][1][2] == pytest.approx(0.0, abs=0.01)


def test_drawn_joints_dont_blink_and_short_gaps_are_bridged():
    frames = [body(i / 15) for i in range(30)]
    for i, v in ((10, 0.45), (11, 0.4), (20, 0.1), (21, 0.1)):
        frames[i].points["left_wrist"].visibility = v   # wobbles under the cut-off, then lost
    drawn = clean_poses(frames)
    assert all(pf.visible("left_wrist") for pf in drawn), "a wobble or a short loss isn't drawn"
    frames = [body(i / 15) for i in range(30)]
    for pf in frames[5:25]:
        pf.points["left_wrist"].visibility = 0.0         # gone for over a second
    assert not clean_poses(frames)[15].visible("left_wrist")


def test_drawn_joints_are_smoothed_without_moving_a_still_body():
    frames = [body(i / 15, dx=0.01 * (-1) ** i) for i in range(30)]  # one-pixel jitter
    xs = [pf.visible("nose").x for pf in clean_poses(frames)[3:-3]]
    assert max(xs) - min(xs) < 0.01
