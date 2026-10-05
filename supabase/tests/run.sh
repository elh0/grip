#!/usr/bin/env bash
# Apply the migration to a throwaway Postgres database with Supabase stubs, then run checks.
# Usage: PGURL=postgres://user@localhost/postgres supabase/tests/run.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
db="grip_test_$$"
psql "${PGURL:?set PGURL}" -qc "create database $db"
trap 'psql "$PGURL" -qc "drop database if exists $db with (force)"' EXIT
url="${PGURL%/*}/$db"
psql "$url" -q -v ON_ERROR_STOP=1 -f "$here/stubs.sql"
psql "$url" -q -v ON_ERROR_STOP=1 -f "$here/../migrations/0001_init.sql"
psql "$url" -q -v ON_ERROR_STOP=1 -f "$here/test.sql"
