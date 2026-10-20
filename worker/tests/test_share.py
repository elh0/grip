"""The shareable clip: render on generated clips, pose over time, the wordmark, the job step."""

import json
import subprocess
from dataclasses import replace

import numpy as np
import pytest
from test_pipeline import SETTINGS, FakeDB, StubClient, StubDetector

from coach_worker import main as worker
from coach_worker import share
from coach_worker.cli import main as cli_main
from coach_worker.pose import Point, PoseFrame, measure
from coach_worker.share import (
    inspect,
    make_share,
    output_size,
    pose_at,
    render_share,
    wordmark,
)

FAST = {"pose_fps": 5}   # keep the stub detector quick; output stays at 30 fps


class MovingDetector(StubDetector):
    """The stub figure, drifting right through the clip, so interpolation has work to do."""

    def detect(self, path, t):
        pf = super().detect(path, t)
        pts = {n: Point(min(0.95, p.x + 0.04 * t), p.y, p.visibility)
               for n, p in pf.points.items()}
        return measure(PoseFrame(t=t, points=pts))


class NoBody:
    def detect(self, path, t):
        return None

    def close(self):
        pass


def lavfi(out, video, audio=None, seconds=2):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"{video}:duration={seconds}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"{audio}:duration={seconds}", "-c:a", "aac", "-shortest"]
    subprocess.run(cmd + ["-pix_fmt", "yuv420p", str(out)], check=True)
    return out


def streams(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of",
                          "json", str(path)], check=True, capture_output=True, text=True).stdout
    data = json.loads(out)
    by_type = {s["codec_type"]: s for s in data["streams"]}
    return by_type, float(data["format"]["duration"])


def frame_at(path, t, w, h):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(path),
                          "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3)


def test_output_size_caps_long_side_and_stays_even():
    assert output_size(1920, 1080) == (1080, 608)
    assert output_size(1080, 1920) == (608, 1080)
    assert output_size(3840, 2160) == (1080, 608)
    assert output_size(320, 240) == (320, 240)      # never upscaled
    assert output_size(641, 361) == (640, 360)       # odd sides rounded to even


def test_render_small_clip(clip, tmp_path):
    out = render_share(clip, tmp_path / "share.mp4", MovingDetector(), tmp_path / "work", **FAST)
    s, duration = streams(out)
    v = s["video"]
    assert (v["codec_name"], v["pix_fmt"], v["width"], v["height"]) == ("h264", "yuv420p", 320, 240)
    assert v["avg_frame_rate"] == "30/1" and int(v["nb_frames"]) == 180
    assert abs(duration - 6.0) < 0.1 and "audio" not in s
    data = out.read_bytes()
    assert data.index(b"moov") < data.index(b"mdat")   # +faststart


def test_render_caps_duration_and_size_and_copies_aac(tmp_path):
    src = lavfi(tmp_path / "big.mp4", "testsrc=size=1920x1080:rate=30", "sine=frequency=440",
                seconds=3)
    out = render_share(src, tmp_path / "share.mp4", StubDetector(), tmp_path / "work",
                       max_seconds=1.5, **FAST)
    s, duration = streams(out)
    assert (s["video"]["width"], s["video"]["height"]) == (1080, 608)
    assert s["audio"]["codec_name"] == "aac"
    assert abs(duration - 1.5) < 0.1


def test_render_draws_blue_body_and_wordmark(tmp_path):
    src = lavfi(tmp_path / "dark.mp4", "color=c=black:size=640x360:rate=30")
    out = render_share(src, tmp_path / "share.mp4", StubDetector(), tmp_path / "work", **FAST)
    f = frame_at(out, 1.0, 640, 360).astype(int)
    blue = (abs(f[..., 0] - 74) < 40) & (abs(f[..., 1] - 116) < 40) & (f[..., 2] > 200)
    assert blue[:, 250:400].sum() > 200                 # the stub figure sits mid-frame
    corner = f[300:, 540:]
    assert (corner.min(axis=2) > 180).sum() > 30        # white wordmark, bottom right
    assert f[:60, :100].max() < 40                      # and no other text or chrome


def test_render_without_a_body_skips(clip, tmp_path):
    assert render_share(clip, tmp_path / "share.mp4", NoBody(), tmp_path / "w", **FAST) is None
    assert not (tmp_path / "share.mp4").exists()


def test_make_share_without_pose_skips(clip, tmp_path):
    assert make_share(clip, tmp_path / "share.mp4", "", tmp_path) is None


def pf(t, x):
    return measure(PoseFrame(t=t, points={"left_hip": Point(x, 0.5), "right_hip": Point(x, 0.6),
                                          "nose": Point(x, 0.1, 0.0)}))


def test_pose_at_interpolates_holds_and_drops():
    poses = [pf(0.0, 0.2), pf(0.2, 0.3), pf(2.0, 0.9)]
    mid = pose_at(poses, 0.1)
    assert mid.visible("left_hip").x == pytest.approx(0.25)
    assert mid.com == pytest.approx((0.25, 0.55))
    assert mid.visible("nose") is None                  # invisible on both sides stays hidden
    assert pose_at(poses, 0.3).t == 0.2                 # held just past the last sample
    assert pose_at(poses, 1.0) is None                  # lost in the long gap
    assert pose_at([], 1.0) is None


def test_pose_at_never_morphs_between_bodies():
    poses = [pf(0.0, 0.2), pf(0.2, 0.8)]                # tracker hopped to another person
    assert pose_at(poses, 0.05).t == 0.0 and pose_at(poses, 0.15).t == 0.2


def test_wordmark_raster():
    m = wordmark(40)
    assert m.mode == "RGBA" and m.height == 40 and 60 <= m.width <= 70
    alpha = np.asarray(m)[..., 3]
    assert 0 < alpha.max() <= 255 * 0.85 + 1 and (alpha > 0).mean() > 0.2


# -- the job step -------------------------------------------------------------------------

@pytest.fixture
def stub_pose(monkeypatch):
    monkeypatch.setattr(share, "try_detector", lambda path: MovingDetector())
    monkeypatch.setattr(share, "POSE_FPS", 5.0)


def test_job_uploads_share_and_sets_path(clip, stub_pose):
    db = FakeDB(clip, {"id": 1, "session_id": "s1", "attempts": 1})
    assert worker.run_once(db, replace(SETTINGS, anthropic_api_key="x"), StubClient())
    assert ("shares", "u1/s1.mp4", "video/mp4") in db.uploads_typed
    assert db.updates[-1] == {"share_path": "u1/s1.mp4"}
    assert db.shared[0][4:8] == b"ftyp"                # an mp4 was sent
    assert any(u.get("status") == "done" for u in db.updates)
    assert db.finished == [(True, False, None)]


def test_render_failure_never_fails_the_job(clip, stub_pose, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("ffmpeg fell over")

    monkeypatch.setattr(share, "render_share", boom)
    db = FakeDB(clip, {"id": 1, "session_id": "s1", "attempts": 1})
    assert worker.run_once(db, SETTINGS)
    assert db.finished == [(True, False, None)]
    assert db.updates[-1]["status"] == "done"
    assert not any("share_path" in u for u in db.updates)
    assert not any(b == "shares" for b, *_ in db.uploads_typed)


def test_share_upload_failure_never_fails_the_job(clip, stub_pose):
    db = FakeDB(clip, {"id": 1, "session_id": "s1", "attempts": 1})
    real_upload = db.upload

    def upload(bucket, path, src, content_type="image/jpeg"):
        if bucket == "shares":
            raise OSError("storage down")
        return real_upload(bucket, path, src, content_type)

    db.upload = upload
    assert worker.run_once(db, SETTINGS)
    assert db.finished == [(True, False, None)] and db.updates[-1]["status"] == "done"


def test_bjj_gets_no_share(clip, stub_pose):
    db = FakeDB(clip, {"id": 1, "session_id": "s1", "attempts": 1})
    db.sport = "bjj"
    worker.run_once(db, SETTINGS)
    assert not any(b == "shares" for b, *_ in db.uploads_typed)


def test_cli_share(clip, tmp_path, monkeypatch, stub_pose):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "run"
    assert cli_main([str(clip), "--offline", "--share", "--out", str(out)]) == 0
    assert streams(out / "share.mp4")[0]["video"]["codec_name"] == "h264"
    assert inspect(out / "share.mp4").width == 320


def test_cli_share_without_pose(clip, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "run"
    assert cli_main([str(clip), "--offline", "--share", "--out", str(out)]) == 0
    assert not (out / "share.mp4").exists()
    assert "share skipped" in capsys.readouterr().err
