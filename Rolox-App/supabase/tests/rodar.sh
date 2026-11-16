#!/usr/bin/env bash
# Testa a migração num Postgres local (sem Supabase), simulando o schema auth.
# Uso: PGURL=postgres://postgres@localhost:5432 ./supabase/tests/rodar.sh
set -euo pipefail
cd "$(dirname "$0")"
PGURL="${PGURL:-postgres://postgres@localhost:5432}"
psql "$PGURL/postgres" -q -c 'drop database if exists rolox_teste' -c 'create database rolox_teste'
psql "$PGURL/rolox_teste" -q -v ON_ERROR_STOP=1 -f stub_supabase.sql -f ../migrations/20261116000000_rolox_base.sql
psql "$PGURL/rolox_teste" -At -v ON_ERROR_STOP=1 -f rolox_base_test.sql
