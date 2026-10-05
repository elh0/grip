"""Frame sampling and keyframe selection with ffmpeg.

Eight still frames miss fast detail (grip changes, arm wraps), so the athlete can mark
a window ("watch 0:12 to 0:18") and we sample densely there.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass
class Frame:
    t: float  # seconds from the start of the clip
    path: Path
    motion: float = 0.0


@dataclass
class Probe:
    duration: float
    width: int
    height: int


def probe(video: Path) -> Probe:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height:format=duration",
            "-of", "json", str(video),
        ],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(out)
    stream = data["streams"][0]
    return Probe(
        duration=float(data["format"]["duration"]),
        width=int(stream["width"]),
        height=int(stream["height"]),
    )


_TIME = r"(\d+):(\d{1,2})(?:\.(\d+))?"
_WINDOW = re.compile(rf"{_TIME}\s*(?:-|–|to)\s*{_TIME}")


def _secs(m: str, s: str, frac: str | None) -> float:
    return int(m) * 60 + int(s) + (float(f"0.{frac}") if frac else 0.0)


def parse_window(note: str | None) -> tuple[float, float] | None:
    """Find a "0:12 to 0:18" style window in the athlete's note."""
    if not note:
        return None
    match = _WINDOW.search(note)
    if not match:
        return None
    g = match.groups()
    start, end = _secs(*g[0:3]), _secs(*g[3:6])
    return (start, end) if end > start else None


def sample_frames(
    video: Path,
    out_dir: Path,
    fps: float,
    width: int,
    start: float = 0.0,
    end: float | None = None,
    prefix: str = "f",
) -> list[Frame]:
    """Extract JPEGs at `fps` between start and end, scaled to `width`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}"]
    if end is not None:
        cmd += ["-to", f"{end:.3f}"]
    cmd += [
        "-i", str(video),
        "-vf", f"fps={fps},scale={width}:-2",
        "-q:v", "3",
        str(out_dir / f"{prefix}_%05d.jpg"),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    paths = sorted(out_dir.glob(f"{prefix}_*.jpg"))
    return [Frame(t=start + i / fps, path=p) for i, p in enumerate(paths)]


def score_motion(frames: list[Frame]) -> None:
    """Mean absolute grey-level change from the previous frame, in place."""
    prev = None
    for frame in frames:
        with Image.open(frame.path) as im:
            grey = np.asarray(im.convert("L").resize((96, 96)), dtype=np.float32)
        frame.motion = 0.0 if prev is None else float(np.abs(grey - prev).mean())
        prev = grey


def select_keyframes(frames: list[Frame], k: int, window: tuple[float, float] | None = None
                     ) -> list[Frame]:
    """Pick k frames spread over the clip, preferring the most motion in each slice.

    With a window, half the budget goes inside it.
    """
    if k <= 0 or not frames:
        return []
    if len(frames) <= k:
        return list(frames)

    if window:
        inside = [f for f in frames if window[0] <= f.t <= window[1]]
        outside = [f for f in frames if not window[0] <= f.t <= window[1]]
        if inside:
            k_in = min(len(inside), max(1, (k + 1) // 2) if outside else k)
            chosen = _spread(inside, k_in) + _spread(outside, k - k_in)
            return sorted(chosen, key=lambda f: f.t)

    return _spread(frames, k)


def _spread(frames: list[Frame], k: int) -> list[Frame]:
    if k <= 0 or not frames:
        return []
    if len(frames) <= k:
        return list(frames)
    bins = np.array_split(np.arange(len(frames)), k)
    return [max((frames[i] for i in b), key=lambda f: f.motion) for b in bins if len(b)]
