#!/bin/sh
set -eu

python <<'PY'
import os
import socket
import time

host = os.environ.get("DB_HOST")
port = int(os.environ.get("DB_PORT", "5432"))
timeout = int(os.environ.get("DB_WAIT_TIMEOUT", "60"))

if host:
    deadline = time.time() + timeout
    while True:
        try:
            with socket.create_connection((host, port), timeout=2):
                break
        except OSError:
            if time.time() > deadline:
                raise SystemExit(f"Timed out waiting for database at {host}:{port}")
            time.sleep(1)
PY

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
fi

if [ "${COLLECTSTATIC:-0}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
