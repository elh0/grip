"""Worker settings, read from the environment (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader so the worker runs without extra dependencies."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    supabase_url: str = ""
    supabase_service_key: str = ""
    anthropic_api_key: str = ""
    model: str = "claude-opus-5-5"
    effort: str = "high"
    max_keyframes: int = 8
    keyframe_width: int = 768
    sample_fps: float = 6.0
    pose_model_path: str = ""
    worker_id: str = "worker-1"
    poll_interval_s: float = 3.0

    @property
    def offline(self) -> bool:
        """No API key: return rule flags only, never call Claude."""
        return not self.anthropic_api_key

    @classmethod
    def from_env(cls, dotenv: Path | None = Path(".env")) -> Settings:
        if dotenv is not None:
            _load_dotenv(dotenv)
        env = os.environ.get
        return cls(
            supabase_url=env("SUPABASE_URL", "").rstrip("/"),
            supabase_service_key=env("SUPABASE_SERVICE_ROLE_KEY", ""),
            anthropic_api_key=env("ANTHROPIC_API_KEY", ""),
            model=env("COACH_MODEL", cls.model),
            effort=env("COACH_EFFORT", cls.effort),
            max_keyframes=int(env("COACH_MAX_KEYFRAMES", cls.max_keyframes)),
            keyframe_width=int(env("COACH_KEYFRAME_WIDTH", cls.keyframe_width)),
            sample_fps=float(env("COACH_SAMPLE_FPS", cls.sample_fps)),
            pose_model_path=env("POSE_MODEL_PATH", ""),
            worker_id=env("WORKER_ID", cls.worker_id),
            poll_interval_s=float(env("POLL_INTERVAL_S", cls.poll_interval_s)),
        )
