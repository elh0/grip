# grip

An AI coach for boulderers, London first. Film a climb, upload it, and get back at most three
timestamped notes, each tied to a body part, with a cue and a drill; rate each one. A free
New sets feed shows photos of fresh walls at the gyms you follow, with an alert when one goes up.
Climbing only for now; the worker still has BJJ code, parked for a later version.

| Folder | What |
|---|---|
| `mobile/` | Expo SDK 57 app (React Native 0.86, TypeScript, Expo Router) |
| `worker/` | Python 3.11 analysis worker: ffmpeg frames, optional MediaPipe pose, sport rules, Claude critique. Also the `grip-coach` CLI for trying clips locally |
| `supabase/` | Database schema, RLS, storage buckets, job queue, and tests for them |
| `brand/` | Identity v11 files: wordmark, crimp mark, app icons |
| `docs/handover.md` | The product and build handover this repo was rebuilt from |

How it fits together is in [ARCHITECTURE.md](ARCHITECTURE.md).

## Try a clip locally (no database)

Needs Python 3.11 and ffmpeg.

```sh
cd worker
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,pose]"
mkdir -p models && curl -sSfo models/pose_landmarker_lite.task \
  https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task
cp .env.example .env   # add ANTHROPIC_API_KEY, set POSE_MODEL_PATH=models/pose_landmarker_lite.task

grip-coach clip.mp4 --sport climbing --note "crux is 0:04 to 0:07" --out out/clip1
open out/clip1/report.html
```

Without `ANTHROPIC_API_KEY` (or with `--offline`) it runs the tracker and rules only.
On Linux, MediaPipe needs `apt-get install libegl1 libgles2`.

## Run the whole thing

1. **Supabase.** Create a project, then run `supabase/migrations/0001_init.sql` in the SQL
   editor (or `supabase db push` with the CLI). Under Authentication, enable Email and set the
   email template to send the one-time code (`{{ .Token }}`).
2. **Worker.** In `worker/.env` set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and
   `ANTHROPIC_API_KEY`, then run `coach-worker`. To host it: `fly launch --no-deploy
   --copy-config` in `worker/`, `fly secrets set ...`, `fly deploy`.
3. **App.** In `mobile/.env` set `EXPO_PUBLIC_SUPABASE_URL` and `EXPO_PUBLIC_SUPABASE_ANON_KEY`,
   then `npm install` and `npx expo run:ios` (or `run:android`). Camera recording needs a
   development build, not Expo Go. For push notifications run `npx eas-cli@latest init` once so
   the app has an EAS project id.

## Checks

```sh
cd mobile && npm run lint && npm run typecheck && npm test
cd worker && ruff check . && pytest
PGURL=postgres://postgres@localhost/postgres supabase/tests/run.sh
```

CI runs all three on every push and pull request.

## Secrets

Secrets live in `.env` files only (both are git-ignored; see the `.env.example` files).
The worker uses the Supabase service-role key. The app only ever gets the anon key.
