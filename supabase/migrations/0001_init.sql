-- grip: initial schema.
-- Backend names stay neutral (coach, session, critique) so a rename only touches the app UI.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Profiles: one per auth user. Sport, level, goals and injuries feed every prompt.
-- ---------------------------------------------------------------------------
create table public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  display_name text,
  level       text check (level in ('new', 'intermediate', 'advanced', 'elite')),
  goals       text,
  injuries    text,
  push_token  text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id) values (new.id) on conflict do nothing;
  return new;
end $$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- Sessions: one filmed climb or roll.
-- status: draft -> uploaded -> analyzing -> done | failed
-- ---------------------------------------------------------------------------
create type public.sport as enum ('climbing', 'bjj');
create type public.session_status as enum ('draft', 'uploaded', 'analyzing', 'done', 'failed');

create table public.sessions (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users (id) on delete cascade,
  sport         public.sport not null,
  status        public.session_status not null default 'draft',
  title         text,
  athlete_note  text,            -- e.g. "I'm in the blue gi", "watch 0:12 to 0:18"
  video_path    text,            -- object path in the private `videos` bucket
  duration_s    real,
  summary       text,            -- one-line coach summary
  error         text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index sessions_user_created on public.sessions (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Feedback items: at most three notes per session.
-- ---------------------------------------------------------------------------
create type public.severity as enum ('minor', 'moderate', 'major');

create table public.feedback_items (
  id          uuid primary key default gen_random_uuid(),
  session_id  uuid not null references public.sessions (id) on delete cascade,
  position    smallint not null check (position between 1 and 3),
  t_seconds   real not null check (t_seconds >= 0),
  body_part   text not null,
  severity    public.severity not null,
  observation text not null,
  cue         text not null,
  drill       text,
  frame_path  text,              -- object path in the private `frames` bucket
  created_at  timestamptz not null default now(),
  unique (session_id, position)
);

-- ---------------------------------------------------------------------------
-- Job queue. Filled by a trigger when a session goes to `uploaded`.
-- The worker claims with FOR UPDATE SKIP LOCKED (see claim_analysis_job).
-- ---------------------------------------------------------------------------
create type public.job_status as enum ('queued', 'running', 'done', 'failed');

create table public.analysis_jobs (
  id          bigint generated always as identity primary key,
  session_id  uuid not null references public.sessions (id) on delete cascade,
  status      public.job_status not null default 'queued',
  attempts    smallint not null default 0,
  worker_id   text,
  last_error  text,
  created_at  timestamptz not null default now(),
  started_at  timestamptz,
  finished_at timestamptz
);
create index analysis_jobs_queued on public.analysis_jobs (created_at) where status = 'queued';
create unique index analysis_jobs_one_open on public.analysis_jobs (session_id)
  where status in ('queued', 'running');

create or replace function public.enqueue_analysis()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.status = 'uploaded' and (tg_op = 'INSERT' or old.status is distinct from 'uploaded') then
    insert into public.analysis_jobs (session_id) values (new.id) on conflict do nothing;
  end if;
  return new;
end $$;

create trigger sessions_enqueue
  after insert or update of status on public.sessions
  for each row execute function public.enqueue_analysis();

-- Called by the worker (service role) to take the oldest queued job.
create or replace function public.claim_analysis_job(p_worker_id text, p_max_attempts int default 3)
returns setof public.analysis_jobs language plpgsql security definer set search_path = public as $$
begin
  return query
  update public.analysis_jobs j
     set status = 'running', attempts = j.attempts + 1, worker_id = p_worker_id, started_at = now()
   where j.id = (
     select id from public.analysis_jobs
      where status = 'queued' and attempts < p_max_attempts
      order by created_at
      for update skip locked
      limit 1)
  returning j.*;
end $$;
revoke all on function public.claim_analysis_job(text, int) from public, anon, authenticated;

-- updated_at bookkeeping
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

create trigger profiles_touch before update on public.profiles
  for each row execute function public.touch_updated_at();
create trigger sessions_touch before update on public.sessions
  for each row execute function public.touch_updated_at();

-- ---------------------------------------------------------------------------
-- Row level security
-- ---------------------------------------------------------------------------
alter table public.profiles       enable row level security;
alter table public.sessions       enable row level security;
alter table public.feedback_items enable row level security;
alter table public.analysis_jobs  enable row level security;  -- service role only

create policy "own profile" on public.profiles
  for all using (auth.uid() = id) with check (auth.uid() = id);

create policy "own sessions: read" on public.sessions
  for select using (auth.uid() = user_id);
create policy "own sessions: create" on public.sessions
  for insert with check (auth.uid() = user_id and status in ('draft', 'uploaded'));
create policy "own sessions: update" on public.sessions
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Users may set status to draft or uploaded (uploaded again = re-analyse) and edit their
-- own text; results (summary, error, duration) are written by the worker only.
create or replace function public.guard_session_update()
returns trigger language plpgsql as $$
begin
  if current_user = 'authenticated' then
    if new.status is distinct from old.status and new.status not in ('draft', 'uploaded') then
      raise exception 'status % is set by the worker', new.status using errcode = '42501';
    end if;
    new.summary := old.summary;
    new.error := old.error;
    new.duration_s := old.duration_s;
    new.user_id := old.user_id;
  end if;
  return new;
end $$;

create trigger sessions_guard before update on public.sessions
  for each row execute function public.guard_session_update();
create policy "own sessions: delete" on public.sessions
  for delete using (auth.uid() = user_id);

create policy "own feedback: read" on public.feedback_items
  for select using (exists (
    select 1 from public.sessions s where s.id = session_id and s.user_id = auth.uid()));

-- ---------------------------------------------------------------------------
-- Storage: private buckets, files live under <user_id>/...
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('videos', 'videos', false, 524288000, array['video/mp4', 'video/quicktime']),
  ('frames', 'frames', false, 10485760, array['image/jpeg'])
on conflict (id) do nothing;

create policy "own videos: write" on storage.objects
  for insert with check (bucket_id = 'videos' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "own videos: read" on storage.objects
  for select using (bucket_id in ('videos', 'frames') and (storage.foldername(name))[1] = auth.uid()::text);
create policy "own videos: delete" on storage.objects
  for delete using (bucket_id in ('videos', 'frames') and (storage.foldername(name))[1] = auth.uid()::text);

-- ---------------------------------------------------------------------------
-- Realtime: the app watches its own sessions and feedback change.
-- ---------------------------------------------------------------------------
alter publication supabase_realtime add table public.sessions, public.feedback_items;
