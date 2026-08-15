#!/usr/bin/env bash
# One-command setup for a fresh clone: installs backend + frontend deps, creates .env from
# the template, and (once real NEO4J_*/REDIS_URL values are filled in) seeds demo users and
# the starter knowledge graph. Safe to re-run -- every step is idempotent or skips itself
# when already done.
#
#   ./scripts/bootstrap.sh
#
# Prefer containers instead? `docker compose up --build` (see docker-compose.yml) needs
# nothing installed locally except Docker itself.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

command -v python3 >/dev/null || { echo "python3 is required, not found on PATH." >&2; exit 1; }
command -v node >/dev/null || { echo "node is required, not found on PATH." >&2; exit 1; }

say "Backend: virtualenv + dependencies"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements-dev.txt

say "Frontend: npm install"
(cd apps/web && npm install)

say "Environment file"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example -- fill in ANTHROPIC_API_KEY, NEO4J_URI/PASSWORD, REDIS_URL before running the app."
else
  echo ".env already exists, leaving it as-is."
fi

# Required for anything past this point to work: a real Neo4j/Redis to talk to.
set +u
# shellcheck disable=SC1091
source .env 2>/dev/null || true
set -u
if [ -z "${NEO4J_PASSWORD:-}" ] || [[ "${NEO4J_URI:-}" == *xxxxxxxx* ]]; then
  say "Skipping seed step"
  echo "NEO4J_URI/NEO4J_PASSWORD not filled in yet -- fill in .env, then run:"
  echo "  source .venv/bin/activate"
  echo "  python3 -m services.integration.seed_users"
  echo "  python3 -m packages.domain.kg.ingest"
else
  say "Seeding demo users"
  python3 -m services.integration.seed_users
  say "Ingesting starter knowledge graph"
  python3 -m packages.domain.kg.ingest
fi

say "Done"
cat <<'EOF'
Start the backend:
  source .venv/bin/activate
  uvicorn services.api.main:app --port 8000

Start the frontend (separate terminal):
  cd apps/web && npm run dev

Then open http://localhost:3000 -- demo credentials are in
docs/governance/demo_login_credentials.md
EOF
