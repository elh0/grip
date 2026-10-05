-- Behaviour checks for 0001_init.sql. Any failed assert aborts with an error.
\set ON_ERROR_STOP on
grant all on all tables in schema public to authenticated, service_role;
grant all on all sequences in schema public to authenticated, service_role;
grant all on storage.objects to authenticated;
grant execute on all functions in schema public to service_role;

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-000000000001', 'a@x'),
  ('00000000-0000-0000-0000-000000000002', 'b@x');

do $$ begin
  assert (select count(*) from public.profiles) = 2, 'profiles created by trigger';
end $$;

-- As user A: create a draft, then mark it uploaded -> one job queued.
set role authenticated;
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
insert into public.sessions (id, user_id, sport, video_path)
values ('10000000-0000-0000-0000-000000000001', auth.uid(), 'climbing', 'x/clip.mp4');
update public.sessions set status = 'uploaded' where id = '10000000-0000-0000-0000-000000000001';
update public.sessions set title = 'Moon 6B+' where id = '10000000-0000-0000-0000-000000000001';

do $$ begin
  -- users can't mark their own session done
  begin
    update public.sessions set status = 'done' where id = '10000000-0000-0000-0000-000000000001';
    raise exception 'user set status=done';
  exception when insufficient_privilege or check_violation then null;
  end;
  -- storage: own folder only
  insert into storage.objects (bucket_id, name)
    values ('videos', '00000000-0000-0000-0000-000000000001/a.mp4');
  begin
    insert into storage.objects (bucket_id, name)
      values ('videos', '00000000-0000-0000-0000-000000000002/a.mp4');
    raise exception 'wrote into another user''s folder';
  exception when insufficient_privilege then null;
  end;
end $$;

-- As user B: sees nothing of A's.
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
do $$ begin
  assert (select count(*) from public.sessions) = 0, 'B cannot see A''s sessions';
  assert (select count(*) from public.profiles) = 1, 'B sees only own profile';
end $$;

-- Worker (service role): claim, write feedback, finish.
reset role;
set role service_role;
do $$
declare j public.analysis_jobs;
begin
  assert (select count(*) from public.analysis_jobs) = 1, 'exactly one job queued';
  select * into j from public.claim_analysis_job('w1');
  assert j.status = 'running' and j.attempts = 1, 'claimed';
  assert (select count(*) from public.claim_analysis_job('w2')) = 0, 'nothing left to claim';
  insert into public.feedback_items (session_id, position, t_seconds, body_part, severity,
    observation, cue, drill)
  values (j.session_id, 1, 4.2, 'Left hip', 'major', 'Hip off the wall.', 'Turn it in.', 'x');
  begin
    insert into public.feedback_items (session_id, position, t_seconds, body_part, severity,
      observation, cue) values (j.session_id, 4, 1, 'x', 'minor', 'x', 'x');
    raise exception 'allowed a fourth note';
  exception when check_violation then null;
  end;
  update public.sessions set status = 'done' where id = j.session_id;
  update public.analysis_jobs set status = 'done', finished_at = now() where id = j.id;
end $$;

-- A can read the feedback and rename the finished session, but not rewrite the summary;
-- B can't see it.
reset role;
set role authenticated;
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
do $$ begin assert (select count(*) from public.feedback_items) = 0; end $$;
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
update public.sessions set title = 'Renamed', summary = 'hacked'
  where id = '10000000-0000-0000-0000-000000000001';
do $$ begin
  assert (select count(*) from public.feedback_items) = 1, 'A reads own feedback';
  assert (select title from public.sessions) = 'Renamed', 'A can rename a done session';
  assert (select summary from public.sessions) is null, 'summary is worker-only';
end $$;
-- Uploading again queues a fresh job.
update public.sessions set status = 'uploaded' where id = '10000000-0000-0000-0000-000000000001';
reset role;
do $$ begin
  assert (select count(*) from public.analysis_jobs where status = 'queued') = 1, 're-queued';
end $$;
reset role;
select 'migration tests passed' as result;
