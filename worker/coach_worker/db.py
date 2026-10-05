"""Supabase over plain HTTP (PostgREST + Storage) with the service-role key."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


class Supabase:
    def __init__(self, url: str, service_key: str, client: httpx.Client | None = None):
        if not url or not service_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        self.url = url.rstrip("/")
        self.http = client or httpx.Client(timeout=60)
        self.headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}

    # -- PostgREST -------------------------------------------------------------
    def _rest(self, method: str, path: str, **kw: Any) -> Any:
        headers = {**self.headers, "Prefer": "return=representation", **kw.pop("headers", {})}
        r = self.http.request(method, f"{self.url}/rest/v1/{path}", headers=headers, **kw)
        r.raise_for_status()
        return r.json() if r.content else None

    def claim_job(self, worker_id: str, max_attempts: int = 3) -> dict | None:
        rows = self._rest("POST", "rpc/claim_analysis_job",
                          json={"p_worker_id": worker_id, "p_max_attempts": max_attempts})
        return rows[0] if rows else None

    def get_session(self, session_id: str) -> dict:
        rows = self._rest("GET", "sessions", params={"id": f"eq.{session_id}", "select": "*"})
        if not rows:
            raise LookupError(f"session {session_id} not found")
        return rows[0]

    def get_profile(self, user_id: str) -> dict:
        rows = self._rest("GET", "profiles", params={"id": f"eq.{user_id}", "select": "*"})
        return rows[0] if rows else {}

    def update_session(self, session_id: str, **fields: Any) -> None:
        self._rest("PATCH", "sessions", params={"id": f"eq.{session_id}"}, json=fields)

    def replace_feedback(self, session_id: str, items: list[dict]) -> None:
        self._rest("DELETE", "feedback_items", params={"session_id": f"eq.{session_id}"})
        if items:
            self._rest("POST", "feedback_items",
                       json=[{**it, "session_id": session_id} for it in items])

    def finish_job(self, job_id: int, ok: bool, error: str | None = None,
                   retry: bool = False) -> None:
        status = "done" if ok else ("queued" if retry else "failed")
        finished = None if status == "queued" else datetime.now(UTC).isoformat()
        self._rest("PATCH", "analysis_jobs", params={"id": f"eq.{job_id}"},
                   json={"status": status, "last_error": error, "finished_at": finished})

    # -- Storage ---------------------------------------------------------------
    def download(self, bucket: str, object_path: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self.http.stream("GET", f"{self.url}/storage/v1/object/{bucket}/{object_path}",
                              headers=self.headers) as r:
            r.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in r.iter_bytes():
                    fh.write(chunk)
        return dest

    def upload(self, bucket: str, object_path: str, src: Path,
               content_type: str = "image/jpeg") -> str:
        r = self.http.post(
            f"{self.url}/storage/v1/object/{bucket}/{object_path}",
            headers={**self.headers, "Content-Type": content_type, "x-upsert": "true"},
            content=src.read_bytes(),
        )
        r.raise_for_status()
        return object_path

    # -- Push ------------------------------------------------------------------
    def push(self, token: str | None, title: str, body: str, data: dict) -> None:
        if not token:
            return
        with contextlib.suppress(httpx.HTTPError):  # a missed push never fails the job
            self.http.post(EXPO_PUSH_URL, json={"to": token, "title": title, "body": body,
                                                "data": data, "sound": "default"})
