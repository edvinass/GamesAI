#!/usr/bin/env bash
# Create the local PostgreSQL user and database for GamesAI (no Docker).
set -euo pipefail

POSTGRES_USER="${POSTGRES_USER:-gamesai}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-gamesai}"
POSTGRES_DB="${POSTGRES_DB:-gamesai}"

if ! command -v psql >/dev/null 2>&1; then
  echo "error: psql not found. Install PostgreSQL first." >&2
  exit 1
fi

echo "==> Setting up local PostgreSQL (${POSTGRES_USER} / ${POSTGRES_DB})"

psql -d postgres -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${POSTGRES_USER}') THEN
    CREATE ROLE ${POSTGRES_USER} WITH LOGIN PASSWORD '${POSTGRES_PASSWORD}';
    RAISE NOTICE 'Created role ${POSTGRES_USER}';
  ELSE
    ALTER ROLE ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';
    RAISE NOTICE 'Role ${POSTGRES_USER} already exists';
  END IF;
END
\$\$;
SQL

if ! psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'" | grep -q 1; then
  psql -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};"
  echo "Created database ${POSTGRES_DB}"
else
  echo "Database ${POSTGRES_DB} already exists"
fi

psql -d postgres -v ON_ERROR_STOP=1 -c "GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_USER};"

# PostgreSQL 15+ does not grant schema privileges by default
psql -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1 <<SQL
GRANT ALL ON SCHEMA public TO ${POSTGRES_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${POSTGRES_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${POSTGRES_USER};
SQL

echo "==> Done. Connection URL:"
echo "postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}"
