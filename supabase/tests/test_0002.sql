-- Behaviour checks for 0002_gyms_sets.sql (runs after test.sql, so users A and B and A's
-- reviewed session exist). Any failed assert aborts with an error.
\set ON_ERROR_STOP on
grant all on all tables in schema public to authenticated, service_role;
grant all on all sequences in schema public to authenticated, service_role;

set role authenticated;
-- A follows BlocFit; B follows BlocFit and Yonder.
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
insert into public.gym_follows (user_id, gym_id) values (auth.uid(), 'blocfit');
-- A tags the climb.
update public.sessions set gym_id = 'blocfit', wall = 'Cave', colour = 'purple', grade = 'V4',
  result = 'sent' where id = '10000000-0000-0000-0000-000000000001';
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
insert into public.gym_follows (user_id, gym_id) values (auth.uid(), 'blocfit'), (auth.uid(), 'yonder');

do $$ begin
  assert (select count(*) from public.gyms) = 33, 'all London gyms visible';
  assert (select count(*) from public.gym_follows) = 2, 'B sees only own follows';
  -- B can't follow on A's behalf
  begin
    insert into public.gym_follows (user_id, gym_id)
      values ('00000000-0000-0000-0000-000000000001', 'yonder');
    raise exception 'followed for someone else';
  exception when insufficient_privilege then null;
  end;
  -- can't post a set with someone else's photo path
  begin
    insert into public.set_posts (user_id, gym_id, photo_path)
      values (auth.uid(), 'blocfit', '00000000-0000-0000-0000-000000000001/x.jpg');
    raise exception 'posted with another user''s photo';
  exception when insufficient_privilege then null;
  end;
end $$;

-- B posts a BlocFit reset -> A (follower) gets an alert, B (poster) doesn't.
insert into public.set_posts (user_id, gym_id, wall, colours, photo_path)
  values (auth.uid(), 'blocfit', 'Cave', '{pink,green}', '00000000-0000-0000-0000-000000000002/s1.jpg');

-- A sees B's post, can't delete it, and rates a note on own session; B can't rate A's note.
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
do $$ begin
  assert (select count(*) from public.set_posts) = 1, 'A sees the new set';
  delete from public.set_posts;
  assert (select count(*) from public.set_posts) = 1, 'A cannot delete B''s post';
  assert (select gym_id from public.sessions) = 'blocfit', 'climb tags saved';
end $$;
insert into public.note_ratings (feedback_item_id, user_id, vote, why)
  select id, auth.uid(), 'down', 'I meant to cut there' from public.feedback_items;
update public.note_ratings set vote = 'up';
insert into public.gym_requests (user_id, name, area) values (auth.uid(), 'New Gym', 'Peckham');

set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
do $$ begin
  assert (select count(*) from public.note_ratings) = 0, 'B cannot see A''s ratings';
  begin
    insert into public.note_ratings (feedback_item_id, user_id, vote)
      select id, auth.uid(), 'up' from public.feedback_items;
    -- B can't even see A's feedback items, so nothing is inserted
    assert (select count(*) from public.note_ratings) = 0, 'B rated A''s note';
  end;
  assert (select count(*) from public.push_outbox) = 0, 'outbox is service-role only';
end $$;

reset role;
do $$ begin
  assert (select count(*) from public.push_outbox) = 1, 'one alert queued';
  assert (select user_id from public.push_outbox) = '00000000-0000-0000-0000-000000000001',
    'alert goes to the follower, not the poster';
  assert (select vote from public.note_ratings) = 'up', 'rating updated';
end $$;

-- A hidden gym drops out of the list, its posts stay visible only to the poster, no alerts.
update public.gyms set hidden = true where id = 'blocfit';
set role authenticated;
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
do $$ begin
  assert (select count(*) from public.gyms) = 32, 'hidden gym not listed';
  assert (select count(*) from public.set_posts) = 0, 'hidden gym posts hidden from others';
end $$;
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
do $$ begin assert (select count(*) from public.set_posts) = 1, 'poster still sees own post'; end $$;
insert into public.set_posts (user_id, gym_id, photo_path)
  values (auth.uid(), 'blocfit', '00000000-0000-0000-0000-000000000002/s2.jpg');
reset role;
do $$ begin assert (select count(*) from public.push_outbox) = 1, 'no alerts for hidden gym'; end $$;
select '0002 tests passed' as result;
