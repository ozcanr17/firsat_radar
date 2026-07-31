#!/bin/sh
set -eu

mkdir -p /data
chown -R radar:radar /data

exec runuser -u radar -- uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
