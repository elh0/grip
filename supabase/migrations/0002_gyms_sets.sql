-- grip: London gyms, new-set posts, follows, alerts, note ratings and climb tags.
-- Scope agreed 16 Oct 2026: climbing only, London first; the feed is free, reviews are paid.

-- ---------------------------------------------------------------------------
-- Climb tags on sessions (gym, wall, hold colour, grade, how it went).
-- ---------------------------------------------------------------------------
alter table public.sessions
  add column gym_id  text,
  add column wall    text,
  add column colour  text,
  add column grade   text,
  add column result  text check (result in ('flash', 'sent', 'fell'));

-- ---------------------------------------------------------------------------
-- Gyms. Readable by everyone signed in; a gym that asks to be hidden disappears
-- from the list and its set posts stay visible only to whoever posted them.
-- ---------------------------------------------------------------------------
create table public.gyms (
  id         text primary key,
  name       text not null,
  area       text,
  city       text not null default 'London',
  website    text,
  instagram  text,
  hidden     boolean not null default false,
  created_at timestamptz not null default now()
);

insert into public.gyms (id, name, area, website) values
  ('blocfit', 'BlocFit', 'Brixton', 'https://www.blocfit.co.uk/'),
  ('stronghold-th', 'Stronghold', 'Tottenham Hale', 'https://www.thestrongholduk.com/'),
  ('stronghold-lf', 'Stronghold', 'London Fields', 'https://www.thestrongholduk.com/'),
  ('arch-b1', 'The Arch, Building One', 'Bermondsey', 'https://www.archclimbingwall.com/'),
  ('arch-north', 'The Arch North', 'North London', 'https://www.archclimbingwall.com/'),
  ('arch-acton', 'The Arch', 'Acton', 'https://www.archclimbingwall.com/'),
  ('arch-sq', 'The Arch', 'Surrey Quays', 'https://www.archclimbingwall.com/'),
  ('vaux-west', 'VauxWall West', 'Vauxhall', 'https://www.vauxwest.co.uk/'),
  ('vaux-east', 'VauxWall East', 'Vauxhall', 'https://www.vauxeast.co.uk/'),
  ('harrowall', 'HarroWall', 'Harrow', 'https://www.harrowall.co.uk/'),
  ('canarywall', 'CanaryWall', 'Canary Wharf', 'https://www.canarywall.co.uk/'),
  ('bethwall', 'BethWall', 'Bethnal Green', 'https://www.bethwall.co.uk/'),
  ('croywall', 'CroyWall', 'Croydon', 'https://www.croywall.co.uk/'),
  ('ravenswall', 'RavensWall', 'Ravenscourt Park', 'https://www.ravenswall.co.uk/'),
  ('castle', 'The Castle', 'Stoke Newington', 'https://www.castle-climbing.co.uk/'),
  ('yonder', 'Yonder', 'Walthamstow', 'https://www.thisisyonder.com/'),
  ('hwbp', 'Hackney Wick Boulder Project', 'Hackney Wick', 'https://hackneywickboulder.co.uk/'),
  ('reach', 'The Reach', 'Woolwich', 'https://www.thereach.org.uk/'),
  ('westway', 'Westway', 'Latimer Road', 'https://www.everyoneactive.com/centre/westway-sports-fitness-centre/climbing/'),
  ('hangar', 'The Climbing Hangar', 'Parsons Green', 'https://www.theclimbinghangar.com/locations/london'),
  ('font', 'The Font', null, 'https://www.the-font.co.uk/'),
  ('west1', 'West1', 'Marylebone', 'https://www.everyoneactive.com/centre/seymour-leisure-centre/climbing-wall/'),
  ('nest', 'The Nest', null, 'https://www.thenestclimbing.co.uk/'),
  ('whitespider', 'White Spider', 'Surbiton', 'https://spiderclimbing.com/white-spider/'),
  ('citybould', 'City Bouldering', 'Aldgate', 'https://www.citybouldering.co.uk/'),
  ('mileend', 'Mile End Climbing Wall', 'Mile End', 'https://www.citybouldering.co.uk/'),
  ('hang', 'Hang.', null, 'https://www.hang.co.uk/'),
  ('substation', 'Substation', 'Brixton', 'https://substation.co.uk/brixton/'),
  ('eustonwall', 'EustonWall', 'Euston', 'https://londonclimbingcentres.co.uk/centre/eustonwall/'),
  ('rise', 'Rise Climbing', null, 'https://www.rise-climbing.com/'),
  ('romford', 'Romford Rock & Boulder', 'Romford', 'https://www.romfordrockandboulder.co.uk/'),
  ('boardroom', 'The Boardroom', 'Wimbledon', 'https://www.theboardroomclimbing.com/wimbledon'),
  ('parthian', 'Parthian', 'Wandsworth', 'https://parthianclimbing.com/wandsworth/');

alter table public.sessions
  add constraint sessions_gym_fk foreign key (gym_id) references public.gyms (id) on delete set null;

-- ---------------------------------------------------------------------------
-- Follows: which gyms send you new-set alerts.
-- ---------------------------------------------------------------------------
create table public.gym_follows (
  user_id    uuid not null references auth.users (id) on delete cascade,
  gym_id     text not null references public.gyms (id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, gym_id)
);

-- ---------------------------------------------------------------------------
-- New-set posts: a climber snaps a fresh wall. Photos live in the `sets` bucket
-- under <user_id>/.
-- ---------------------------------------------------------------------------
create table public.set_posts (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  gym_id     text not null references public.gyms (id) on delete cascade,
  wall       text,
  colours    text[] not null default '{}',
  note       text check (char_length(note) <= 280),
  photo_path text not null,
  created_at timestamptz not null default now()
);
create index set_posts_gym_created on public.set_posts (gym_id, created_at desc);
create index set_posts_created on public.set_posts (created_at desc);

-- ---------------------------------------------------------------------------
-- Alerts outbox: one row per follower when a set is posted. The worker sends
-- them as Expo pushes and stamps sent_at.
-- ---------------------------------------------------------------------------
create table public.push_outbox (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references auth.users (id) on delete cascade,
  title      text not null,
  body       text not null,
  data       jsonb not null default '{}',
  created_at timestamptz not null default now(),
  sent_at    timestamptz
);
create index push_outbox_unsent on public.push_outbox (created_at) where sent_at is null;

create or replace function public.queue_set_alerts()
returns trigger language plpgsql security definer set search_path = public as $$
declare g public.gyms;
begin
  select * into g from public.gyms where id = new.gym_id;
  if g.hidden then return new; end if;
  insert into public.push_outbox (user_id, title, body, data)
  select f.user_id,
         'New set at ' || g.name,
         coalesce(nullif(new.wall, '') || ' has been reset.', 'Fresh climbs just went up.'),
         jsonb_build_object('setId', new.id, 'gymId', g.id)
    from public.gym_follows f
   where f.gym_id = new.gym_id and f.user_id <> new.user_id;
  return new;
end $$;

create trigger set_posts_alert
  after insert on public.set_posts
  for each row execute function public.queue_set_alerts();

-- ---------------------------------------------------------------------------
-- Note ratings: thumbs up or down on each coach note, with an optional reason.
-- ---------------------------------------------------------------------------
create table public.note_ratings (
  feedback_item_id uuid primary key references public.feedback_items (id) on delete cascade,
  user_id          uuid not null references auth.users (id) on delete cascade,
  vote             text not null check (vote in ('up', 'down')),
  why              text check (char_length(why) <= 500),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
create trigger note_ratings_touch before update on public.note_ratings
  for each row execute function public.touch_updated_at();

-- ---------------------------------------------------------------------------
-- "Add your gym" requests.
-- ---------------------------------------------------------------------------
create table public.gym_requests (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  name       text not null check (char_length(name) between 1 and 120),
  area       text check (char_length(area) <= 120),
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Row level security
-- ---------------------------------------------------------------------------
alter table public.gyms         enable row level security;
alter table public.gym_follows  enable row level security;
alter table public.set_posts    enable row level security;
alter table public.push_outbox  enable row level security;  -- service role only
alter table public.note_ratings enable row level security;
alter table public.gym_requests enable row level security;

create policy "gyms: read visible" on public.gyms
  for select to authenticated using (not hidden);

create policy "own follows" on public.gym_follows
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "sets: read" on public.set_posts
  for select to authenticated using (
    auth.uid() = user_id
    or exists (select 1 from public.gyms g where g.id = gym_id and not g.hidden));
create policy "sets: post own" on public.set_posts
  for insert with check (
    auth.uid() = user_id and split_part(photo_path, '/', 1) = auth.uid()::text);
create policy "sets: delete own" on public.set_posts
  for delete using (auth.uid() = user_id);

create policy "ratings: own notes" on public.note_ratings
  for all using (auth.uid() = user_id)
  with check (auth.uid() = user_id and exists (
    select 1 from public.feedback_items fi join public.sessions s on s.id = fi.session_id
     where fi.id = feedback_item_id and s.user_id = auth.uid()));

create policy "requests: send own" on public.gym_requests
  for insert with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- Storage: `sets` bucket. Anyone signed in can see set photos; you only write
-- and delete under your own folder.
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('sets', 'sets', false, 10485760, array['image/jpeg', 'image/png', 'image/heic'])
on conflict (id) do nothing;

create policy "sets photos: write own" on storage.objects
  for insert with check (bucket_id = 'sets' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "sets photos: read" on storage.objects
  for select to authenticated using (bucket_id = 'sets');
create policy "sets photos: delete own" on storage.objects
  for delete using (bucket_id = 'sets' and (storage.foldername(name))[1] = auth.uid()::text);

alter publication supabase_realtime add table public.set_posts;
