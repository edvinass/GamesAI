#!/bin/sh
set -e
alembic upgrade head
# Listen on IPv6 so Railway private networking can reach this service.
exec uvicorn app.main:app --host "::" --port "${PORT:-8000}"
