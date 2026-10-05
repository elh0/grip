# Architecture

```
 phone (Expo)                       Supabase                          worker (Python, Fly.io)
 ─────────────                      ────────                          ───────────────────────
 record / pick clip
 insert session (draft) ──────────▶ sessions
 PUT clip to signed URL ──────────▶ storage: videos/<user>/<session>.mp4
 set status = uploaded ───────────▶ trigger ─▶ analysis_jobs (queued)
                                                    ▲
                                                    └──── claim_analysis_job()  (FOR UPDATE SKIP LOCKED)
                                                          download clip
                                                          frames → pose → rules → Claude
                                    feedback_items ◀───── write ≤ 3 notes
                                    storage: frames ◀──── upload the frames notes point at
                                    sessions (done) ◀──── summary, duration
 realtime update  ◀──────────────── sessions / feedback_items
 push notification ◀────────────────────────────────────── Expo push
```

Backend names stay neutral (`coach`, `session`, `critique`) so a rename only touches the app UI.

## Database (`supabase/migrations/0001_init.sql`)

- `profiles`: one per user, created by trigger. Level, goals and injuries feed every prompt;
  `push_token` is where the app stores its Expo push token.
- `sessions`: `draft → uploaded → analyzing → done | failed`. Users can only set `draft` or
  `uploaded` (uploading again re-queues the review); results are worker-only, enforced by the
  `guard_session_update` trigger.
- `feedback_items`: at most three per session (`position` 1 to 3), each with time, body part,
  severity, observation, cue, drill and the frame it was seen in.
- `analysis_jobs`: filled by a trigger when a session becomes `uploaded`, one open job per
  session. The worker claims the oldest with `claim_analysis_job()`; failed jobs retry up to
  three times.
- Storage: private `videos` and `frames` buckets, files under `<user_id>/`, owner-only policies.
- RLS everywhere; the jobs table has no user policies (service role only).

## Worker (`worker/coach_worker/`)

`analyze.py` is the seam: `analyze(video, ctx, settings, work_dir) -> Analysis`.

1. `frames.py` samples the clip at `COACH_SAMPLE_FPS` and scores motion between frames. If the
   athlete's note names a window ("watch 0:12 to 0:18") it samples three times denser there.
2. `pose.py` (optional, MediaPipe) finds the fifteen points from the identity, measures knee,
   elbow and hip angles and a rough centre of mass, and draws the blue wireframe, the
   centre-of-mass trail and the centre line onto keyframes.
3. `sports/` turns poses into hints: climbing flags bent arms while static and foot cuts; BJJ
   flags flared elbows and being flat on the back. They are hints for the coach, never verdicts.
4. `frames.select_keyframes` picks `COACH_MAX_KEYFRAMES` frames spread across the clip, the
   highest-motion frame in each slice, with half the budget inside the athlete's window.
5. `critique.py` sends the frames, profile, flags and joint angles to Claude
   (`claude-opus-5-5`, structured output via `messages.parse`, `fallbacks: "default"`), then
   enforces the product rules: three notes at most, in clip order, timestamps inside the clip.
   Without an API key it returns the strongest tracker flags instead (offline mode).

`main.py` is the job loop; `cli.py` (`grip-coach`) runs one clip with no database and writes
`critique.json`, the keyframes and `report.html`.

## App (`mobile/src/`)

- `app/sign-in.tsx`: email one-time code.
- `app/index.tsx`: sessions list with live status.
- `app/record.tsx`: pick Climb or Roll, add a note, film (expo-camera) or choose a clip
  (expo-image-picker), upload with progress (expo-file-system upload task to a signed URL).
- `app/session/[id].tsx`: player (expo-video), timeline with a tick per note, summary and cue
  cards; tapping a card jumps to that moment. Live status while it's being reviewed. Delete.
- `lib/`: Supabase client, upload, push registration, feedback helpers (tested).
- `constants/theme.ts` + `brand-tokens.json`: identity v11. Dark to look, light to decide:
  video and playback on black, lists and choices on white. Mat blue only for the wordmark, the
  crimp and the tracked body; notes, markers and buttons are black or white. Host Grotesk and
  DM Mono, regular weight only.

## Known limits

- BJJ: tangled bodies break single-person pose and labels swap. For now the athlete's note
  ("I'm in the blue gi") tells the coach who to review.
- Eight stills miss fast detail (grip changes, arm wraps); the note window helps.
- Climbing filmed from directly behind can't show hip-to-wall distance; the app asks for
  side-on or 45°.
- Never yet run against a real Claude critique, a real Supabase project or real footage.
