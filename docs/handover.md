# Send & Roll: app build handover

Written 5 Oct 2026 from the original project (first called Digital PT, then plumbline, now Send & Roll / "grip"). This covers the code, stack, what's done and next, blockers, accounts, website and marketing ideas, and competitors. Brand and design history is deliberately left out because the brand is being redesigned elsewhere.

**In this folder:** `HANDOVER.md` (this file) and `send-and-roll-code.zip`, which holds `app/` (mobile app, Supabase schema, Python worker), `prototype/` (pipeline proof of concept) and `research/competitors.md`.

---

## 1. The product in one paragraph

An AI coach for climbers and grapplers. You film a board session or a jiu-jitsu roll, upload it, and get back **at most three** timestamped technique notes, each tied to a body part, with a cue and a drill ("0:42, left hip drifting off the wall, turn the hip in and flag right"). It's for people aged roughly 20 to 40 who train three or more times a week and already film themselves. Over time it should remember recurring faults, like a coach who's watched all your sessions. **Climbing board first, BJJ second.**

## 2. Stack (decided, nobody has overridden it)

| Layer | Choice |
|---|---|
| Mobile | Expo SDK 57, React Native 0.86, TypeScript, Expo Router (`app/mobile`) |
| Recording | `expo-camera` (video mode) plus `expo-image-picker` for clips already on the phone |
| Upload | `expo-file-system` upload task with progress, PUT to a Supabase Storage signed URL |
| Backend | Supabase: Postgres with RLS, Auth (email OTP now; Apple, Google and magic link planned), private Storage buckets `videos` and `frames`, Realtime |
| Job queue | `analysis_jobs` table filled by a trigger when a session goes to `uploaded`; worker claims with `FOR UPDATE SKIP LOCKED` |
| Worker | Python 3.11 (`app/worker`): ffmpeg frames, optional MediaPipe pose, sport rules, then a Claude critique. Container host: Fly.io by default, Modal if GPUs are needed |
| Critique model | Claude `claude-opus-5-5` with structured JSON output (`messages.parse`), `fallbacks: "default"` |
| Notifications | Expo push when analysis finishes |
| Builds | EAS (`eas build`, `eas submit`, `eas update`) |

Backend names are kept neutral (`coach`, `session`, `critique`) so a rename only touches the app UI. The app's display name, slug and URL scheme are still `plumbline` in `app/mobile/app.json` and `package.json`, so rename them to the new name.

## 3. Code map

**`app/`** (start with `app/ARCHITECTURE.md`, then `app/README.md`)
- `mobile/src/app/`: `sign-in.tsx` (email code), `index.tsx` (sessions list), `record.tsx` (pick sport, film or pick, upload with progress), `session/[id].tsx` (player, severity markers on the timeline, summary, cue cards, live status).
- `mobile/src/lib/`: Supabase client, upload, types, feedback helpers (with tests). `mobile/src/components/`: cue card, timeline, pill button, session row.
- `mobile/src/constants/brand-tokens.json` and `theme.ts`: the old plumbline tokens. `npm run sync-brand` copies from `../../brand/tokens.json`, a path that won't exist in the new project. Point it at the new brand tokens or drop the script.
- `supabase/migrations/0001_init.sql`: `profiles`, `sessions`, `analysis_jobs`, `feedback_items`, RLS, storage buckets, queue trigger.
- `worker/coach_worker/`: `main.py` (job loop), `analyze.py` (**the seam**: `analyze(video, ctx) -> Critique`), `frames.py`, `pose.py`, `sports/` (climbing, bjj rules), `critique.py` (system prompt and Claude call), `db.py`, `config.py`. Tests in `worker/tests/`.

**`prototype/`** (standalone, see its README)
- FastAPI upload page plus CLI. MediaPipe Pose Landmarker (model bundled in `coach/models/`) at about 6 fps, joint-angle metrics, sport rule flags, 8 motion-weighted keyframes with the skeleton drawn on, then a Claude coach review as structured JSON.
- Runs in offline mode (rule flags only) when no `ANTHROPIC_API_KEY` is set.
- Linux needs `apt-get install libegl1 libgles2` for MediaPipe.

**How to run** (full steps in `app/README.md`)
1. Create a Supabase project, run the migration, enable email OTP.
2. Worker: copy `.env.example` to `.env`, then add the service-role key and the Anthropic key. Run `pip install -e ".[dev]"` then `coach-worker`. It needs ffmpeg. For pose metrics, run `pip install -e ".[pose]"` and set `POSE_MODEL_PATH` (you can reuse the prototype's `.task` file).
3. App: copy `.env.example` to `.env` with the Supabase URL and anon key, then `npm install` and `npx expo run:ios`. Camera recording needs a dev build, not Expo Go.
4. Tests: `cd mobile && npm test && npm run typecheck`, and `cd worker && pytest`.

## 4. What's done

- The app scaffold is complete across all four screens and styled to the old brand. Typecheck, 5 app tests and 14 worker tests pass, and the Android bundle builds (all checked 2 Oct).
- The worker runs the full pipeline end to end on a generated clip with Claude stubbed out. The request shape sent to Claude was checked.
- The prototype runs pose, keyframes, overlays, CLI and web upload end to end on a sample street clip. A request with a fake key reached the API and was rejected only for the key, so its shape is accepted.
- **Never tested:** a real Claude critique, a real Supabase database, and real climbing or BJJ footage. Linting isn't set up yet, because the environment couldn't download the config.
- **Not in git and not deployed.** The code only exists as files and in this zip.

## 5. Next steps (in order)

1. Put the code in a git repo, ideally a monorepo with `mobile/`, `worker/` and `supabase/`, and set up lint.
2. **Get an Anthropic API key** and run the prototype on 5 to 10 real board and rolling clips. Feedback quality is the main open question.
3. Create the Supabase project and run one clip through the app end to end.
4. Merge the prototype's frame selection and prompts into `worker/coach_worker/analyze.py`, `frames.select_keyframes` and `critique.SYSTEM`.
5. Rename and rebrand the app (`app.json`, package name, theme tokens, icons, copy).
6. Onboarding (sport, level, goals and injuries feed every prompt), push notifications, delete-session flow, Apple and Google sign-in, then moving tokens from AsyncStorage to SecureStore.
7. Climbing pose metrics, then multi-person pose for BJJ (RTMPose or YOLO-pose, plus a tracker or tap-to-select "that's me").
8. Recurring-faults history (`faults` table plus a join from feedback items).
9. TestFlight and the Google Play internal track via EAS.

**Known pipeline limits to plan around**
- BJJ: tangled bodies break pose tracking and P1/P2 labels swap. For now, the athlete's note ("I'm in the blue gi") tells the coach who to review.
- Eight still frames miss fast detail like grip changes and arm wraps. Fix: let the user mark a window ("watch 0:12 to 0:18") and sample densely there.
- Climbing filmed from directly behind can't show hip-to-wall distance. Prompt users to film side-on or at 45°.
- Board detection (Moon, Kilter, Tension have fixed layouts) would let the coach name holds and moves.
- Cost is about 8 images plus text per review on Opus, a few cents a run. The frame cap and resolution are worker config (`COACH_MAX_KEYFRAMES`, `COACH_KEYFRAME_WIDTH`).

## 6. Blockers and accounts

**Nothing about developer accounts was set up or discussed in this project.** These are the accounts the build will need, with prices as I understand them (check them when you sign up):

| Account | Why | Cost |
|---|---|---|
| Anthropic Console (API key) | Real critiques. **This is the main blocker right now.** | Pay as you go |
| Supabase | Auth, database, storage, realtime | Free tier to start |
| Apple Developer Program | TestFlight and the App Store, plus Sign in with Apple (required by App Store rules once Google sign-in is offered) | $99 a year |
| Google Play Console | Android internal track and the store | $25 one-off |
| Expo account (EAS) | Cloud builds, store submits, OTA updates | Free tier to start |
| Worker host (Fly.io, or Modal for GPU) | Runs the Python analysis worker | Usage-based |
| Domain, Instagram handle, trademark | For the final name: confirm at a registrar and search classes 9, 41 and 42 (USPTO, UKIPO, EUIPO). Instagram and registry lookups couldn't be checked from the old project | Varies |

Secrets go in `.env` files only. Both `.env.example` files list what's needed. The worker uses the Supabase service-role key, and the app only ever gets the anon key.

## 7. Website and marketing ideas

- **Landing page draft:** https://claude.ai/artifact/3CFLq8ut8HSDjCHEfDedfV. It still uses the plumbline name and old brand, so treat it as a structure reference. Sections: a hero with a climber on a board, a plumb line and fix notes drawn over the frame; how it works; a sample review that flips between climbing and BJJ; a progress chart; an FAQ; a beta signup. The signup form doesn't save emails yet, and all the stats and sample sessions on it are made up.
- **Positioning angles** (from the competitor scan):
  - **Board climbing first.** Kilter, Moon and Tension sessions are short, repeatable and filmed from a fixed angle, and no competitor targets them. Kilter's app was recently pulled from the stores, so that community is churning.
  - **Climbing and BJJ in one app.** Nobody else does both, but check that the overlap audience is real before leading with it.
  - **Calm, not gamified.** Every rival is dark mode with one loud accent, scores out of 100, streaks and XP. A light, honest "coach who's rewatched your tape" with three notes, not twenty, stands out.
  - **Voice:** short, specific, dry, on the athlete's side. Speak the sport (beta, flag, drop-knee, underhook, base) without explaining it. No hype, no emoji, no "unlock your potential".
- **Pricing signal:** the market runs from per-analysis credits (Cima, about $0.50 each) to subscriptions ($10 to $25 a month). SmartBJJ meters by minutes of footage, which maps neatly onto our real cost (frames multiplied by Claude calls).
- **Marketing ideas carried over:** shareable cue cards (a frame with the line plus one note) as social tiles, a beta waitlist on the landing page, and seeding with board-climbing communities and local BJJ gyms. For credibility, collect 20 to 30 clips per sport with a real coach's notes and compare them against the app's output. That also gives you marketing material.

## 8. Competitors (full table in `research/competitors.md` in the zip)

- **Climbing:** Climbah ($6.99 a week to $119.99 a year), Bouldering AI: Coach (iOS, solo dev), Cima (credits), Obstacle IQ (pitched as much to ninja and obstacle-course athletes) and rok. (EU, waitlist).
- **BJJ:** **SmartBJJ** is the closest match (iOS, rolls scored out of 10 with timestamped corrections, $9.99 to $99.99 a month metered by minutes). MatIQ hasn't launched. mmaGPT and JAB AI are multi-discipline.
- **Adjacent:** Sportsbox AI for golf ($299 a year) and SwingVision for tennis prove people pay for the phone video, pose and coaching pattern.
- **Risk:** the barrier to entry is low, and most rivals are solo-dev apps on the same LLM and pose stack. The moat has to be critique quality, the board focus and the brand.
- **Visual gallery** of all seven apps: https://claude.ai/artifact/6TtRQL5ztU71uW8Mkd8qWn. The screenshots stayed in the old project and aren't in the zip.

## 9. Brand pointer (old, being replaced)

The old plumbline brand files are in the original project under `brand/` (`brand-guidelines.md` v0.4, `tokens.css`, `tokens.json`, `naming.md`). They used paper #F3F3F0, ink #111111 and a lime #C8F03C accent, with Geist for UI. The app UI rule worth keeping whatever the new brand is: **dark to look, light to decide**, meaning video and playback sit on dark screens, while lists and choices sit on light ones.
