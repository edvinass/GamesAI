#!/bin/sh
set -e

if [ -z "$BACKEND_URL" ]; then
    echo "BACKEND_URL is required" >&2
    exit 1
fi

# Strip accidental quotes and trailing slashes from Railway variable values.
BACKEND_URL=$(printf '%s' "$BACKEND_URL" | tr -d '"' | sed 's#/*$##')
export BACKEND_URL
export PORT="${PORT:-8080}"

echo "Starting Caddy on port ${PORT}, proxying API to ${BACKEND_URL}"

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
