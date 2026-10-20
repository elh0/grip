"""Job loop: claim a queued analysis, run it, write notes back, push the athlete."""

from __future__ import annotations

import logging
import signal
import tempfile
import time
from pathlib import Path

from . import share
from .analyze import Analysis, analyze
from .config import Settings
from .critique import CoachContext, CritiqueError
from .db import Supabase
from .frames import probe
from .sports import get_sport

log = logging.getLogger("coach_worker")
MAX_ATTEMPTS = 3
SHARE_BUCKET = "shares"


def make_client(settings: Settings):
    if settings.offline:
        return None
    import anthropic

    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def feedback_rows(analysis: Analysis, frame_paths: dict[float, str]) -> list[dict]:
    rows = []
    for i, note in enumerate(analysis.critique.notes, 1):
        kf = analysis.frame_for(note.t_seconds)
        rows.append({
            "position": i,
            "t_seconds": note.t_seconds,
            "body_part": note.body_part,
            "severity": note.severity,
            "observation": note.observation,
            "cue": note.cue,
            "drill": note.drill,
            "frame_path": frame_paths.get(kf.t) if kf else None,
        })
    return rows


def process_job(job: dict, db: Supabase, settings: Settings, client=None) -> None:
    session = db.get_session(job["session_id"])
    profile = db.get_profile(session["user_id"])
    sid, uid = session["id"], session["user_id"]
    db.update_session(sid, status="analyzing", error=None)

    with tempfile.TemporaryDirectory(prefix=f"grip-{sid}-") as tmp:
        work = Path(tmp)
        video = db.download("videos", session["video_path"], work / "clip")
        meta = probe(video)
        ctx = CoachContext(
            sport=get_sport(session["sport"]),
            duration_s=meta.duration,
            level=profile.get("level"),
            goals=profile.get("goals"),
            injuries=profile.get("injuries"),
            athlete_note=session.get("athlete_note"),
        )
        analysis = analyze(video, ctx, settings, work / "analysis", client=client)

        # Upload only the frames a note points at.
        frame_paths: dict[float, str] = {}
        for note in analysis.critique.notes:
            kf = analysis.frame_for(note.t_seconds)
            if kf and kf.t not in frame_paths:
                frame_paths[kf.t] = db.upload("frames", f"{uid}/{sid}/{kf.t:08.2f}.jpg", kf.path)

        db.replace_feedback(sid, feedback_rows(analysis, frame_paths))
        db.update_session(sid, status="done", summary=analysis.critique.summary,
                          duration_s=round(meta.duration, 2))

        n = len(analysis.critique.notes)
        db.push(profile.get("push_token"), "Your review is ready",
                f"{n} note{'s' if n != 1 else ''} on your session." if n else "No notes this time.",
                {"sessionId": sid})

        # After the push: the review is what they're waiting for, the share can follow.
        if session["sport"] == "climbing":
            share_session(db, settings, video, uid, sid, work / "share", analysis.poses)


def share_session(db: Supabase, settings: Settings, video: Path, uid: str, sid: str,
                  work: Path, poses: list | None = None) -> str | None:
    """Render, upload and record the shareable tracked clip. Never fails the job."""
    try:
        out = share.make_share(video, work / "share.mp4", settings.pose_model_path, work,
                               poses=poses)
        if not out:
            return None
        path = db.upload(SHARE_BUCKET, f"{uid}/{sid}.mp4", out, content_type="video/mp4")
        db.update_session(sid, share_path=path)
        log.info("share for session %s at %s/%s", sid, SHARE_BUCKET, path)
        return path
    except Exception:  # noqa: BLE001 - a missing share never fails the review
        log.exception("share for session %s failed", sid)
        return None


def run_once(db: Supabase, settings: Settings, client=None) -> bool:
    """Claim and process one job. Returns False when the queue is empty."""
    job = db.claim_job(settings.worker_id, MAX_ATTEMPTS)
    if not job:
        return False
    log.info("job %s session %s (attempt %s)", job["id"], job["session_id"], job["attempts"])
    try:
        process_job(job, db, settings, client)
    except Exception as exc:  # noqa: BLE001 - every failure is recorded on the job
        retry = not isinstance(exc, CritiqueError | ValueError) and job["attempts"] < MAX_ATTEMPTS
        log.exception("job %s failed (retry=%s)", job["id"], retry)
        db.finish_job(job["id"], ok=False, error=str(exc)[:2000], retry=retry)
        if not retry:
            db.update_session(job["session_id"], status="failed",
                              error="We couldn't review this clip. Try filming it again.")
        return True
    db.finish_job(job["id"], ok=True)
    return True


def send_alerts(db: Supabase) -> int:
    """Push queued new-set alerts to followers. Returns how many were handled."""
    alerts = db.unsent_alerts()
    for a in alerts:
        db.push(a.get("push_token"), a["title"], a["body"], a.get("data") or {})
    db.mark_alerts_sent([a["id"] for a in alerts])
    return len(alerts)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    db = Supabase(settings.supabase_url, settings.supabase_service_key)
    client = make_client(settings)
    log.info("worker %s up (model=%s, offline=%s)", settings.worker_id, settings.model,
             settings.offline)

    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping:
        try:
            busy = run_once(db, settings, client)
            busy = send_alerts(db) > 0 or busy
        except Exception:  # noqa: BLE001 - keep the loop alive through network blips
            log.exception("poll failed")
            busy = False
        if not busy:
            time.sleep(settings.poll_interval_s)


if __name__ == "__main__":
    run()
