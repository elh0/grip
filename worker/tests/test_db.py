import json

import httpx

from coach_worker.db import Supabase


def make(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return Supabase("https://x.supabase.co/", "svc", client)


def test_claim_job_calls_rpc_with_service_key():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["auth"] = str(req.url), req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=[{"id": 7, "session_id": "s", "attempts": 1}])

    job = make(handler).claim_job("w1")
    assert job["id"] == 7
    assert seen["url"] == "https://x.supabase.co/rest/v1/rpc/claim_analysis_job"
    assert seen["auth"] == "Bearer svc"
    assert seen["body"] == {"p_worker_id": "w1", "p_max_attempts": 3}


def test_claim_job_empty():
    assert make(lambda r: httpx.Response(200, json=[])).claim_job("w1") is None


def test_replace_feedback_deletes_then_inserts():
    calls = []

    def handler(req):
        calls.append((req.method, req.url.path, req.url.params.get("session_id")))
        return httpx.Response(201 if req.method == "POST" else 204)

    make(handler).replace_feedback("s1", [{"position": 1}])
    assert calls == [("DELETE", "/rest/v1/feedback_items", "eq.s1"),
                     ("POST", "/rest/v1/feedback_items", None)]


def test_finish_job_retry_requeues():
    bodies = []

    def handler(req):
        bodies.append(json.loads(req.content))
        return httpx.Response(204)

    db = make(handler)
    db.finish_job(1, ok=False, error="x", retry=True)
    db.finish_job(1, ok=True)
    assert bodies[0]["status"] == "queued" and bodies[0]["finished_at"] is None
    assert bodies[1]["status"] == "done" and bodies[1]["finished_at"]


def test_storage_roundtrip(tmp_path):
    def handler(req):
        if req.method == "GET":
            return httpx.Response(200, content=b"video")
        assert req.headers["x-upsert"] == "true"
        return httpx.Response(200, json={"Key": "frames/a.jpg"})

    db = make(handler)
    dest = db.download("videos", "u/s.mp4", tmp_path / "v.mp4")
    assert dest.read_bytes() == b"video"
    assert db.upload("frames", "u/s/1.jpg", dest) == "u/s/1.jpg"


def test_push_swallows_errors():
    def handler(req):
        raise httpx.ConnectError("down")

    make(handler).push("tok", "t", "b", {})  # no exception
    make(handler).push(None, "t", "b", {})
