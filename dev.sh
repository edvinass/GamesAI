#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PID=""
FRONTEND_PID=""

log() {
  printf '\n\033[1;36m==>\033[0m %s\n' "$*"
}

warn() {
  printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2
}

die() {
  printf '\033[1;31merror:\033[0m %s\n' "$*" >&2
  exit 1
}

cleanup() {
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    log "Stopping frontend (pid $FRONTEND_PID)"
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "Stopping backend (pid $BACKEND_PID)"
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

ensure_env() {
  if [[ ! -f .env ]]; then
    cp .env.example .env
    log "Created .env from .env.example"
  fi

  set -a
  # shellcheck disable=SC1091
  source .env
  set +a

  export POSTGRES_USER="${POSTGRES_USER:-gamesai}"
  export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-gamesai}"
  export POSTGRES_DB="${POSTGRES_DB:-gamesai}"
  export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}}"
  export DATABASE_URL="${DATABASE_URL/@postgres:/@localhost:}"
  export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173,http://localhost:3000}"
}

start_postgres() {
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    log "Starting PostgreSQL (Docker)"
    docker compose up -d postgres

    log "Waiting for PostgreSQL"
    for _ in $(seq 1 30); do
      if docker compose exec -T postgres pg_isready -U "$POSTGRES_USER" >/dev/null 2>&1; then
        return
      fi
      sleep 1
    done

    die "PostgreSQL did not become ready in time"
  fi

  if ! command -v psql >/dev/null 2>&1; then
    die "PostgreSQL is required. Install PostgreSQL locally or start Docker."
  fi

  if ! (nc -z localhost 5432 2>/dev/null || psql -d postgres -c "SELECT 1" >/dev/null 2>&1); then
    die "PostgreSQL is not running on localhost:5432. Start it with: brew services start postgresql@18"
  fi

  log "Using local PostgreSQL (no Docker)"
  bash "$ROOT/scripts/setup-local-db.sh"
}

setup_backend() {
  log "Setting up backend"
  if [[ ! -d backend/.venv ]]; then
    python3 -m venv backend/.venv
  fi

  # shellcheck disable=SC1091
  source backend/.venv/bin/activate
  pip install -q -r backend/requirements.txt
}

setup_frontend() {
  log "Setting up frontend"
  if [[ ! -d frontend/node_modules ]]; then
    npm install --prefix frontend
  fi
}

start_backend() {
  log "Running database migrations"
  # shellcheck disable=SC1091
  source backend/.venv/bin/activate
  if ! (cd backend && alembic upgrade head); then
    die "Database migration failed. Run: ./scripts/setup-local-db.sh"
  fi

  log "Starting backend on http://localhost:8000"
  (cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) &
  BACKEND_PID=$!
}

start_frontend() {
  log "Starting frontend on http://localhost:5173"
  npm run dev --prefix frontend &
  FRONTEND_PID=$!
}

run_docker() {
  log "Starting full stack with Docker Compose"
  docker compose up --build
}

run_local() {
  ensure_env
  start_postgres
  setup_backend
  setup_frontend
  start_backend
  start_frontend

  log "GamesAI is running"
  echo "  Frontend:  http://localhost:5173"
  echo "  Backend:   http://localhost:8000"
  echo "  API docs:  http://localhost:8000/docs"
  echo ""
  echo "Press Ctrl+C to stop."

  wait "$BACKEND_PID" "$FRONTEND_PID"
}

usage() {
  cat <<EOF
Usage: ./dev.sh [command]

Commands:
  (default)   Start backend + frontend (Postgres via Docker if available, else local)
  docker      Start everything with Docker Compose
  db          Create local PostgreSQL user and database only
  help        Show this help message
EOF
}

case "${1:-}" in
  docker)
    ensure_env
    run_docker
    ;;
  db)
    ensure_env
    bash "$ROOT/scripts/setup-local-db.sh"
    ;;
  help|-h|--help)
    usage
    ;;
  "")
    run_local
    ;;
  *)
    die "Unknown command: $1 (run ./dev.sh help)"
    ;;
esac
