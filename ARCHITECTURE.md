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
- `app/(tabs)/`: four tabs with a custom mono tab bar.
  - `index.tsx` Climbs: your filmed climbs with gym, wall, colour, grade, result and live status.
  - `sets.tsx` New sets: the free feed of fresh-wall photos, Following or All London. Live.
  - `gyms.tsx` Gyms: every London gym, follow for alerts, a Coming soon card (wall maps),
    Add your gym.
- `app/gym/[id].tsx`: one gym, its website, its sets, "Be the first to post a set" when empty.
- `app/post-set.tsx`: photo (camera or library), gym, wall, new colours, note.
- `app/record.tsx`: tag the climb (gym, wall, colour, grade, flash/sent/fell), add a note, film
  (expo-camera) or choose a clip (expo-image-picker), upload with progress.
- `app/session/[id].tsx`: player (expo-video), timeline with a tick per note, summary and cue
  cards; tapping a card jumps to that moment. Each note has Helped / Not for me and an optional
  reason (`note_ratings`). Live status while it's being reviewed. Delete.
- `lib/`: Supabase client, upload, push registration, feedback and climb helpers (tested),
  `gyms.tsx` (gyms, follows, set posts), `ratings.ts`, `use-sets.ts`.

Migration `0002_gyms_sets.sql` adds the climb tags, 33 London gyms, `gym_follows`, `set_posts`
(photos in the private `sets` bucket), `note_ratings`, `gym_requests` and `push_outbox`: a
trigger queues "New set at …" for each follower and the worker sends them as Expo pushes.
Migration `0003_projects_plans.sql` adds `projects` (a boulder you keep going back to, in a gym
or outdoors: next-go note, reset date, one pinned per climber; a send or flash on a linked climb
marks it sent), `sessions.project_id` and the worker-only `sessions.share_path`, `entitlements`
(periods of Grip from Apple, referrals, creator offers or by hand), `review_uses` and
`review_allowance()` (3 reviews a month free, 20 with Grip; `enqueue_analysis` refuses the upload
past the limit, re-uploading a climb is free), referral codes with `redeem_referral()` (both get a
free month, a referrer earns at most 12), and the private `shares` bucket for tracked clips.
- `app/(tabs)/you.tsx` You: your project (next-go note, reset countdown), other projects, the
  grade pyramid of sends (a climb counts once, flashes filled), your plan and invite.
- `app/project/[id].tsx`: new or edit a project; `app/plans.tsx`: Free and Grip cards, the
  founding offer, your invite code and a box for a friend's. Purchases wait for the App Store build.
- `widgets/your-project.tsx`: the "Your project" home and lock screen widget (expo-widgets);
  `lib/widget.ts` pushes the current project to it whenever projects load.
- `components/opening.tsx`: the opening screen, the crimp fingertip presses the i and lets go.
- `constants/theme.ts` + `brand-tokens.json`: identity v11. Black backgrounds, #0D0E0D tiles,
  white text. Mat blue only for the wordmark, the crimp and the tracked body; notes, markers
  and buttons are white. Host Grotesk and DM Mono, regular weight only.

## Known limits

- BJJ: tangled bodies break single-person pose and labels swap. For now the athlete's note
  ("I'm in the blue gi") tells the coach who to review.
- Eight stills miss fast detail (grip changes, arm wraps); the note window helps.
- Climbing filmed from directly behind can't show hip-to-wall distance; the app asks for
  side-on or 45°.
- Never yet run against a real Claude critique, a real Supabase project or real footage.
