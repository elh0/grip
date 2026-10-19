"""End to end on a generated clip: analyze(), the CLI, and the job loop with fakes."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from coach_worker import main as worker
from coach_worker.analyze import analyze
from coach_worker.cli import main as cli_main
from coach_worker.config import Settings
from coach_worker.critique import CoachContext, Critique, Note
from coach_worker.pose import Point, PoseFrame, measure
from coach_worker.sports import get_sport

SETTINGS = Settings(max_keyframes=6, keyframe_width=160, sample_fps=4)


class StubClient:
    def __init__(self):
        self.calls = []
        self.messages = self

    def parse(self, **kw):
        self.calls.append(kw)
        notes = [Note(t_seconds=2.0, body_part="Left hip", severity="major",
                      observation="Hip swings off the wall.", cue="Turn the left hip in.",
                      drill="Five slow repeats of the move, hip first.")]
        return SimpleNamespace(stop_reason="end_turn",
                               parsed_output=Critique(summary="One thing.", notes=notes))


class StubDetector:
    """Pretend pose: a figure whose left arm is bent and still, so climbing rules fire."""

    def detect(self, path, t):
        pts = {n: Point(0.5, 0.5) for n in (
            "nose", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
            "left_wrist", "right_wrist", "left_hip", "right_hip", "left_knee", "right_knee",
            "left_ankle", "right_ankle", "left_foot", "right_foot")}
        pts.update(left_shoulder=Point(0.45, 0.3), left_elbow=Point(0.45, 0.45),
                   left_wrist=Point(0.55, 0.45), right_shoulder=Point(0.55, 0.3),
                   left_hip=Point(0.46, 0.6), right_hip=Point(0.54, 0.6))
        return measure(PoseFrame(t=t, points=pts))

    def close(self):
        pass


def ctx(note=None):
    return CoachContext(sport=get_sport("climbing"), duration_s=6.0, athlete_note=note)


def test_analyze_offline(clip, tmp_path):
    a = analyze(clip, ctx(), SETTINGS, tmp_path)
    assert a.offline and len(a.keyframes) == 6 and a.pose_frames == 0
    assert a.critique.notes == []


def test_analyze_with_pose_and_coach(clip, tmp_path):
    client = StubClient()
    a = analyze(clip, ctx("watch 0:02 to 0:04"), replace(SETTINGS, anthropic_api_key="x"),
                tmp_path, client=client, detector=StubDetector())
    assert not a.offline and a.pose_frames > 0
    assert any(f.body_part == "Left arm" for f in a.flags)
    assert sum(1 for k in a.keyframes if 2.0 <= k.t <= 4.0) >= 3
    assert all("keyframes" in str(k.path) for k in a.keyframes)  # wireframes drawn
    images = [b for b in client.calls[0]["messages"][0]["content"] if b["type"] == "image"]
    assert len(images) == 6
    assert a.frame_for(2.1).t == min((k.t for k in a.keyframes), key=lambda t: abs(t - 2.1))


def test_cli_offline(clip, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "run"
    assert cli_main([str(clip), "--sport", "climbing", "--offline", "--out", str(out)]) == 0
    result = json.loads((out / "critique.json").read_text())
    assert result["offline"] and len(result["frames"]) == 8
    assert (out / "report.html").read_text().startswith("<!doctype html>")
    assert all((out / f["file"]).is_file() for f in result["frames"])


class FakeDB:
    def __init__(self, clip: Path, job=None):
        self.clip, self.job = clip, job
        self.updates, self.feedback, self.uploads, self.finished, self.pushes = [], [], [], [], []
        self.uploads_typed, self.shared, self.sport = [], [], "climbing"

    def claim_job(self, worker_id, max_attempts):
        job, self.job = self.job, None
        return job

    def get_session(self, sid):
        return {"id": sid, "user_id": "u1", "sport": self.sport, "video_path": "u1/s1.mp4",
                "athlete_note": None}

    def get_profile(self, uid):
        return {"level": "intermediate", "push_token": "ExponentPushToken[x]"}

    def update_session(self, sid, **fields):
        self.updates.append(fields)

    def download(self, bucket, path, dest):
        dest.write_bytes(self.clip.read_bytes())
        return dest

    def upload(self, bucket, path, src, content_type="image/jpeg"):
        if bucket == "frames":
            self.uploads.append((bucket, path))
        else:
            self.shared.append(src.read_bytes())
        self.uploads_typed.append((bucket, path, content_type))
        return path

    def replace_feedback(self, sid, rows):
        self.feedback = rows

    def finish_job(self, job_id, ok, error=None, retry=False):
        self.finished.append((ok, retry, error))

    def push(self, token, title, body, data):
        self.pushes.append((token, body))


def test_job_loop_success(clip):
    db = FakeDB(clip, {"id": 1, "session_id": "s1", "attempts": 1})
    settings = replace(SETTINGS, anthropic_api_key="x")
    assert worker.run_once(db, settings, StubClient()) is True
    assert db.updates[0]["status"] == "analyzing" and db.updates[-1]["status"] == "done"
    assert db.feedback[0]["position"] == 1 and db.feedback[0]["frame_path"].startswith("u1/s1/")
    assert db.uploads == [("frames", db.feedback[0]["frame_path"])]
    assert db.finished == [(True, False, None)]
    assert db.pushes == [("ExponentPushToken[x]", "1 note on your session.")]
    assert worker.run_once(db, settings, StubClient()) is False


def test_job_loop_failure_marks_session(clip):
    db = FakeDB(clip, {"id": 2, "session_id": "s1", "attempts": 3})
    db.download = lambda *a: (_ for _ in ()).throw(OSError("storage down"))
    assert worker.run_once(db, SETTINGS) is True
    assert db.finished[0][:2] == (False, False)
    assert db.updates[-1]["status"] == "failed"


def test_job_loop_retries_transient_errors(clip):
    db = FakeDB(clip, {"id": 3, "session_id": "s1", "attempts": 1})
    db.download = lambda *a: (_ for _ in ()).throw(OSError("blip"))
    worker.run_once(db, SETTINGS)
    assert db.finished[0][:2] == (False, True)
    assert db.updates[-1]["status"] == "analyzing"


def test_send_alerts_pushes_each_and_marks_sent():
    class AlertDB:
        def __init__(self):
            self.pushes, self.marked = [], []

        def unsent_alerts(self):
            return [{"id": 5, "push_token": "tok", "title": "New set at Yonder", "body": "b",
                     "data": {"gymId": "yonder"}},
                    {"id": 6, "push_token": None, "title": "t", "body": "b", "data": {}}]

        def push(self, token, title, body, data):
            self.pushes.append((token, title))

        def mark_alerts_sent(self, ids):
            self.marked = ids

    db = AlertDB()
    assert worker.send_alerts(db) == 2
    assert db.pushes[0] == ("tok", "New set at Yonder") and db.marked == [5, 6]
