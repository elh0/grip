"""Run one clip locally, no Supabase: the old prototype, folded into the worker.

    grip-coach clip.mp4 --sport climbing --note "watch 0:04 to 0:07" --out out/run1

Writes critique.json, the keyframes the coach saw (with the wireframe when pose runs)
and a small report.html. Without ANTHROPIC_API_KEY it runs offline (tracker flags only).
--share also writes share.mp4, the tracked clip (needs pose: POSE_MODEL_PATH).
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
import tempfile
from pathlib import Path

from .analyze import analyze
from .config import Settings
from .critique import CoachContext, fmt_time
from .frames import probe
from .main import make_client
from .share import make_share
from .sports import get_sport


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="grip-coach", description=__doc__.splitlines()[0])
    ap.add_argument("video", type=Path)
    ap.add_argument("--sport", choices=["climbing", "bjj"], default="climbing")
    ap.add_argument("--note", help="what to watch, e.g. \"I'm in the blue gi\"")
    ap.add_argument("--level")
    ap.add_argument("--goals")
    ap.add_argument("--injuries")
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--offline", action="store_true", help="skip the Claude call")
    ap.add_argument("--share", action="store_true", help="also render share.mp4")
    args = ap.parse_args(argv)

    if not args.video.is_file():
        ap.error(f"no such file: {args.video}")

    settings = Settings.from_env()
    sport = get_sport(args.sport)
    meta = probe(args.video)
    ctx = CoachContext(sport=sport, duration_s=meta.duration, level=args.level,
                       goals=args.goals, injuries=args.injuries, athlete_note=args.note)
    client = None if args.offline else make_client(settings)

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    analysis = analyze(args.video, ctx, settings, out / "work", client=client)

    frames_dir = out / "frames"
    frames_dir.mkdir(exist_ok=True)
    frames = []
    for i, kf in enumerate(analysis.keyframes, 1):
        dest = frames_dir / f"{i:02d}_{kf.t:06.2f}.jpg"
        shutil.copy(kf.path, dest)
        frames.append({"t": kf.t, "file": f"frames/{dest.name}"})
    shutil.rmtree(out / "work", ignore_errors=True)

    result = {
        "sport": sport.key,
        "duration_s": round(meta.duration, 2),
        "offline": analysis.offline,
        "pose_frames": analysis.pose_frames,
        "flags": [f.__dict__ for f in analysis.flags],
        "critique": analysis.critique.model_dump(),
        "frames": frames,
    }
    (out / "critique.json").write_text(json.dumps(result, indent=2))
    (out / "report.html").write_text(render_report(result, sport.filming_tip))

    print(analysis.critique.summary)
    for n in analysis.critique.notes:
        print(f"{fmt_time(n.t_seconds)}  {n.body_part}: {n.observation} -> {n.cue}")
    print(f"\nwrote {out / 'critique.json'} and {out / 'report.html'}", file=sys.stderr)

    if args.share:
        with tempfile.TemporaryDirectory(prefix="grip-share-") as tmp:
            made = make_share(args.video, out / "share.mp4", settings.pose_model_path, Path(tmp))
        print(f"wrote {made}" if made else "share skipped: no pose (set POSE_MODEL_PATH and "
              "pip install -e \".[pose]\") or no body found", file=sys.stderr)
    return 0


def render_report(result: dict, tip: str) -> str:
    e = html.escape
    c = result["critique"]
    notes = "".join(
        f"<li><span class=m>{fmt_time(n['t_seconds'])} &nbsp; {e(n['body_part'].upper())}</span>"
        f"<p>{e(n['observation'])}</p><p><b>{e(n['cue'])}</b></p>"
        f"<p class=q>{e(n['drill'])}</p></li>"
        for n in c["notes"]
    )
    frames = "".join(
        f"<figure><img src='{f['file']}'><figcaption class=m>{fmt_time(f['t'])}</figcaption>"
        "</figure>" for f in result["frames"]
    )
    mode = "OFFLINE" if result["offline"] else "COACH"
    return f"""<!doctype html><meta charset=utf-8><title>grip review</title>
<style>
body{{background:#000;color:#F3F3F0;font:16px/1.4 "Host Grotesk",Helvetica,sans-serif;
margin:24px;max-width:960px}}
.m{{font-family:"DM Mono",ui-monospace,monospace;font-size:12px;letter-spacing:.04em;
color:rgba(243,243,240,.55)}}
ol{{list-style:none;padding:0}}li{{border-top:1px solid rgba(243,243,240,.16);padding:12px 0}}
p{{margin:4px 0}}b{{font-weight:400}}.q{{color:rgba(243,243,240,.55)}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px}}
figure{{margin:0}}img{{width:100%;display:block}}
</style>
<p class=m>{mode} &nbsp; {e(result['sport'].upper())} &nbsp; {fmt_time(result['duration_s'])}</p>
<p>{e(c['summary'])}</p><ol>{notes}</ol>
<div class=g>{frames}</div><p class=m>{e(tip)}</p>
"""


if __name__ == "__main__":
    raise SystemExit(main())
