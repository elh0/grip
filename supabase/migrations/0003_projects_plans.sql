-- grip: projects, sends, review allowance, plans, referrals and shareable tracked clips.
-- Agreed 19 Oct 2026: free = 3 reviews a month, Grip = up to 20; referrals give both people a
-- free month; every reviewed climb gets a shareable clip with the blue tracking, free included.

-- ---------------------------------------------------------------------------
-- Projects: the boulder you keep going back to, in a gym or outdoors. The widget shows
-- the pinned project (or the latest open one) with your next-go note and when it resets.
-- ---------------------------------------------------------------------------
create table public.projects (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  name       text check (char_length(name) <= 80),
  gym_id     text references public.gyms (id) on delete set null,
  place      text check (char_length(place) <= 120),  -- outdoors: crag or boulder
  wall       text check (char_length(wall) <= 80),
  colour     text check (char_length(colour) <= 40),
  grade      text check (char_length(grade) <= 20),
  status     text not null default 'open' check (status in ('open', 'sent', 'dropped')),
  pinned     boolean not null default false,
  next_note  text check (char_length(next_note) <= 280),
  resets_on  date,
  sent_at    timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index projects_user on public.projects (user_id, updated_at desc);
create unique index projects_one_pinned on public.projects (user_id) where pinned;
create trigger projects_touch before update on public.projects
  for each row execute function public.touch_updated_at();

alter table public.sessions
  add column project_id uuid references public.projects (id) on delete set null,
  add column share_path text;  -- worker-only: shares/<user>/<session>.mp4

-- A send or flash on a project's climb marks the project sent.
create or replace function public.mark_project_sent()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.project_id is not null and new.result in ('flash', 'sent')
     and (tg_op = 'INSERT' or old.result is distinct from new.result
          or old.project_id is distinct from new.project_id) then
    update public.projects
       set status = 'sent', sent_at = coalesce(sent_at, now()), pinned = false
     where id = new.project_id and user_id = new.user_id and status <> 'sent';
  end if;
  return new;
end $$;
create trigger sessions_project_sent
  after insert or update of result, project_id on public.sessions
  for each row execute function public.mark_project_sent();

-- Users can't set the share path, and can only link their own projects.
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
    new.share_path := old.share_path;
  end if;
  return new;
end $$;

-- Not security definer: the RLS on projects is what limits users to their own.
create or replace function public.guard_session_project()
returns trigger language plpgsql as $$
begin
  if new.project_id is not null and not exists (
       select 1 from public.projects p where p.id = new.project_id and p.user_id = new.user_id) then
    raise exception 'not your project' using errcode = '42501';
  end if;
  if tg_op = 'INSERT' and current_user = 'authenticated' then new.share_path := null; end if;
  return new;
end $$;
create trigger sessions_guard_project before insert or update of project_id on public.sessions
  for each row execute function public.guard_session_project();

-- ---------------------------------------------------------------------------
-- Plans. One row per period of Grip: an Apple subscription (written by the server from
-- App Store notifications), a referral month, a creator offer, or one granted by hand.
-- ---------------------------------------------------------------------------
create table public.entitlements (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  source     text not null check (source in ('apple', 'referral', 'creator', 'manual')),
  plan       text not null default 'grip' check (plan in ('grip', 'founding')),
  starts_at  timestamptz not null default now(),
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  check (expires_at > starts_at)
);
create index entitlements_user on public.entitlements (user_id, expires_at desc);

create or replace function public.has_grip(p_user uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.entitlements e
                  where e.user_id = p_user and now() >= e.starts_at and now() < e.expires_at)
$$;

-- ---------------------------------------------------------------------------
-- Review allowance: 3 a month free, 20 with Grip. A session uses one review the first
-- time it's uploaded; re-uploading the same climb doesn't use another.
-- ---------------------------------------------------------------------------
create table public.review_uses (
  id         bigint generated always as identity primary key,
  -- Deleting a climb keeps its use, so delete and re-film doesn't reset the count.
  session_id uuid references public.sessions (id) on delete set null,
  user_id    uuid not null references auth.users (id) on delete cascade,
  created_at timestamptz not null default now()
);
create unique index review_uses_session on public.review_uses (session_id) where session_id is not null;
create index review_uses_user_month on public.review_uses (user_id, created_at);

create or replace function public.review_allowance_for(p_user uuid)
returns table (used int, allowed int, has_grip boolean, resets_on date)
language sql stable security definer set search_path = public as $$
  select (select count(*)::int from public.review_uses u
           where u.user_id = p_user and u.created_at >= date_trunc('month', now())),
         case when public.has_grip(p_user) then 20 else 3 end,
         public.has_grip(p_user),
         (date_trunc('month', now()) + interval '1 month')::date
$$;
revoke all on function public.review_allowance_for(uuid) from public, anon, authenticated;

-- What the app shows: your own allowance only.
create or replace function public.review_allowance()
returns table (used int, allowed int, has_grip boolean, resets_on date)
language sql stable security definer set search_path = public as $$
  select * from public.review_allowance_for(auth.uid())
$$;

create or replace function public.enqueue_analysis()
returns trigger language plpgsql security definer set search_path = public as $$
declare a record;
begin
  if new.status = 'uploaded' and (tg_op = 'INSERT' or old.status is distinct from 'uploaded') then
    if not exists (select 1 from public.review_uses where session_id = new.id) then
      select * into a from public.review_allowance_for(new.user_id);
      if a.used >= a.allowed then
        raise exception 'review limit reached'
          using errcode = 'P0001', hint = format('%s of %s reviews used this month', a.used, a.allowed);
      end if;
      insert into public.review_uses (session_id, user_id) values (new.id, new.user_id);
    end if;
    insert into public.analysis_jobs (session_id) values (new.id) on conflict do nothing;
  end if;
  return new;
end $$;

-- ---------------------------------------------------------------------------
-- Referrals: share your code, and when a new climber uses it you both get a free month.
-- A referrer earns at most 12 months this way.
-- ---------------------------------------------------------------------------
create table public.referral_codes (
  code       text primary key check (code ~ '^[A-Z0-9]{6}$'),
  user_id    uuid not null unique references auth.users (id) on delete cascade,
  created_at timestamptz not null default now()
);
create table public.referrals (
  referred_id uuid primary key references auth.users (id) on delete cascade,
  referrer_id uuid not null references auth.users (id) on delete cascade,
  code        text not null,
  created_at  timestamptz not null default now()
);

create or replace function public.my_referral_code()
returns text language plpgsql security definer set search_path = public as $$
declare c text;
begin
  if auth.uid() is null then raise exception 'sign in first' using errcode = '42501'; end if;
  select code into c from public.referral_codes where user_id = auth.uid();
  while c is null loop
    c := upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 6));
    insert into public.referral_codes (code, user_id) values (c, auth.uid()) on conflict do nothing;
    select code into c from public.referral_codes where user_id = auth.uid();
  end loop;
  return c;
end $$;

create or replace function public.grant_free_month(p_user uuid, p_source text)
returns void language sql security definer set search_path = public as $$
  insert into public.entitlements (user_id, source, starts_at, expires_at)
  select p_user, p_source, s, s + interval '1 month'
    from (select greatest(now(), coalesce(max(expires_at), now())) s
            from public.entitlements where user_id = p_user) t
$$;
revoke all on function public.grant_free_month(uuid, text) from public, anon, authenticated;

create or replace function public.redeem_referral(p_code text)
returns void language plpgsql security definer set search_path = public as $$
declare r uuid;
begin
  if auth.uid() is null then raise exception 'sign in first' using errcode = '42501'; end if;
  select user_id into r from public.referral_codes where code = upper(trim(p_code));
  if r is null then raise exception 'that code doesn''t exist' using errcode = 'P0001'; end if;
  if r = auth.uid() then raise exception 'that''s your own code' using errcode = 'P0001'; end if;
  if exists (select 1 from public.referrals where referred_id = auth.uid()) then
    raise exception 'you''ve already used a code' using errcode = 'P0001';
  end if;
  if (select created_at from public.profiles where id = auth.uid()) < now() - interval '30 days' then
    raise exception 'codes are for new climbers' using errcode = 'P0001';
  end if;
  insert into public.referrals (referred_id, referrer_id, code) values (auth.uid(), r, upper(trim(p_code)));
  perform public.grant_free_month(auth.uid(), 'referral');
  if (select count(*) from public.referrals where referrer_id = r) <= 12 then
    perform public.grant_free_month(r, 'referral');
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- Row level security
-- ---------------------------------------------------------------------------
alter table public.projects       enable row level security;
alter table public.entitlements   enable row level security;
alter table public.review_uses    enable row level security;
alter table public.referral_codes enable row level security;
alter table public.referrals      enable row level security;

create policy "own projects" on public.projects
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own plans: read" on public.entitlements
  for select using (auth.uid() = user_id);
create policy "own review uses: read" on public.review_uses
  for select using (auth.uid() = user_id);
create policy "own code: read" on public.referral_codes
  for select using (auth.uid() = user_id);
create policy "own referrals: read" on public.referrals
  for select using (auth.uid() in (referred_id, referrer_id));

-- ---------------------------------------------------------------------------
-- Storage: tracked share clips, written by the worker, readable by their owner.
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('shares', 'shares', false, 209715200, array['video/mp4'])
on conflict (id) do nothing;

create policy "own shares: read" on storage.objects
  for select using (bucket_id = 'shares' and (storage.foldername(name))[1] = auth.uid()::text);

alter publication supabase_realtime add table public.projects;
