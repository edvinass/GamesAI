#!/bin/sh
set -e

if [ -z "$BACKEND_URL" ]; then
    echo "BACKEND_URL is required" >&2
    exit 1
fi

exec /docker-entrypoint.sh nginx -g 'daemon off;'
