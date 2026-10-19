-- Behaviour checks for 0003_projects_plans.sql (runs after test_0002.sql: users A and B exist,
-- A's session 1 was uploaded before review_uses existed). Any failed assert aborts.
\set ON_ERROR_STOP on
grant all on all tables in schema public to authenticated, service_role;
grant all on all sequences in schema public to authenticated, service_role;
update public.gyms set hidden = false where id = 'blocfit';

set role authenticated;
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
-- A starts a project and links a fell attempt; then sends it.
insert into public.projects (id, user_id, name, gym_id, wall, colour, grade, pinned, next_note, resets_on)
  values ('20000000-0000-0000-0000-000000000001', auth.uid(), 'Cave purple', 'blocfit', 'Cave',
          'purple', 'V5', true, 'Heel higher on the volume', current_date + 9);
insert into public.sessions (id, user_id, sport, project_id, result, share_path)
  values ('10000000-0000-0000-0000-000000000011', auth.uid(), 'climbing',
          '20000000-0000-0000-0000-000000000001', 'fell', 'x/fake.mp4');
do $$ begin
  assert (select status from public.projects) = 'open', 'a fall leaves the project open';
  assert (select share_path from public.sessions where id = '10000000-0000-0000-0000-000000000011') is null,
    'users can''t set share_path';
  -- one pinned project per climber
  begin
    insert into public.projects (user_id, name, pinned) values (auth.uid(), 'Second', true);
    raise exception 'two pinned projects';
  exception when unique_violation then null;
  end;
end $$;

-- Free allowance: session 11 is the first counted review this month; three in total allowed.
update public.sessions set status = 'uploaded' where id = '10000000-0000-0000-0000-000000000011';
insert into public.sessions (id, user_id, sport, status) values
  ('10000000-0000-0000-0000-000000000012', auth.uid(), 'climbing', 'uploaded'),
  ('10000000-0000-0000-0000-000000000013', auth.uid(), 'climbing', 'uploaded');
do $$ begin
  assert (select used from public.review_allowance()) = 3, 'three used';
  assert (select allowed from public.review_allowance()) = 3, 'free allows three';
  begin
    insert into public.sessions (user_id, sport, status) values (auth.uid(), 'climbing', 'uploaded');
    raise exception 'fourth free review allowed';
  exception when raise_exception then null;
  end;
end $$;
-- Re-uploading a reviewed climb doesn't use another review.
update public.sessions set status = 'draft' where id = '10000000-0000-0000-0000-000000000012';
update public.sessions set status = 'uploaded' where id = '10000000-0000-0000-0000-000000000012';
do $$ begin assert (select used from public.review_allowance()) = 3, 're-upload is free'; end $$;

-- The send marks the project sent and unpins it.
update public.sessions set result = 'sent' where id = '10000000-0000-0000-0000-000000000011';
do $$ begin
  assert (select status from public.projects) = 'sent', 'send marks project sent';
  assert not (select pinned from public.projects), 'sent project unpinned';
  assert (select sent_at from public.projects) is not null, 'sent_at stamped';
end $$;

-- B can't see A's project or link a session to it, or read A's allowance.
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
do $$ begin
  assert (select count(*) from public.projects) = 0, 'B can''t see A''s projects';
  begin
    insert into public.sessions (user_id, sport, project_id)
      values (auth.uid(), 'climbing', '20000000-0000-0000-0000-000000000001');
    raise exception 'linked someone else''s project';
  exception when insufficient_privilege then null;
  end;
  assert (select used from public.review_allowance()) = 0, 'B sees only own allowance';
  begin
    perform public.grant_free_month(auth.uid(), 'manual');
    raise exception 'user granted themselves a month';
  exception when insufficient_privilege then null;
  end;
end $$;

-- Referral: A shares a code, B redeems it, both get a month and A can review again.
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
select public.my_referral_code() as a_code \gset
do $$ begin
  assert (select public.my_referral_code()) = (select code from public.referral_codes), 'code is stable';
  begin perform public.redeem_referral(public.my_referral_code());
    raise exception 'redeemed own code';
  exception when raise_exception then null; end;
end $$;
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
select set_config('test.code', :'a_code', false);
select public.redeem_referral(:'a_code');
do $$ begin
  assert (select has_grip from public.review_allowance()), 'B has Grip';
  assert (select allowed from public.review_allowance()) = 20, 'Grip allows twenty';
  begin perform public.redeem_referral(current_setting('test.code'));
    raise exception 'redeemed twice';
  exception when raise_exception then null; end;
end $$;
set request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
insert into public.sessions (user_id, sport, status) values (auth.uid(), 'climbing', 'uploaded');
do $$ begin
  assert (select count(*) from public.entitlements) = 1, 'A sees own month';
  assert (select used from public.review_allowance()) = 4, 'referrer can review again';
end $$;

reset role;
do $$ begin
  assert (select count(*) from public.entitlements) = 2, 'both got a month';
  assert (select count(*) from public.review_uses) = 4, 'four uses logged';
end $$;
-- Deleting a climb keeps its use.
delete from public.sessions where id = '10000000-0000-0000-0000-000000000013';
do $$ begin assert (select count(*) from public.review_uses) = 4, 'delete keeps the use'; end $$;
select '0003 tests passed' as result;
