import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def clip(tmp_path_factory) -> Path:
    """A 6 second 320x240 test clip with motion (ffmpeg testsrc)."""
    out = tmp_path_factory.mktemp("clip") / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         "testsrc=size=320x240:rate=30:duration=6", "-pix_fmt", "yuv420p", str(out)],
        check=True,
    )
    return out
