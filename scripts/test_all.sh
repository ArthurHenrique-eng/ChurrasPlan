#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/BackEnd/Python"
RUN_MYSQL="${RUN_MYSQL:-0}"
RUN_E2E="${RUN_E2E:-0}"

printf '\n== ChurrasPlan: backend unit/integration ==\n'
cd "$BACKEND"
python -m compileall -q .
pytest -q tests

printf '\n== ChurrasPlan: schema e frontend estático ==\n'
cd "$ROOT"
python scripts/validate_schema.py
python scripts/validate_frontend.py
find FrontEnd/js -name '*.js' -print0 | xargs -0 -n1 node --check
node --check FrontEnd/sw.js

if [[ "$RUN_MYSQL" == "1" ]]; then
  : "${MYSQL_TEST_URL:?Defina MYSQL_TEST_URL para RUN_MYSQL=1}"
  printf '\n== ChurrasPlan: MySQL real + Alembic ==\n'
  export DATABASE_URL="$MYSQL_TEST_URL"
  cd "$BACKEND"
  alembic upgrade head
  alembic check
  pytest -q tests_mysql
fi

if [[ "$RUN_E2E" == "1" ]]; then
  printf '\n== ChurrasPlan: E2E Playwright ==\n'
  cd "$ROOT"
  export E2E_BASE_URL="${E2E_BASE_URL:-http://127.0.0.1:5500}"
  pytest -q e2e
fi

printf '\nTodos os testes selecionados passaram.\n'
