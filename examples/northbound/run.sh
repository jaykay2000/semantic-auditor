#!/usr/bin/env bash
# Run Northbound from examples/northbound/:  ./run.sh   (PORT=8080 NORTHBOUND_RELEASE=2.3 by default)
cd "$(dirname "$0")" || exit 1
exec python3 -m uvicorn northbound.app:app --host 127.0.0.1 --port "${PORT:-8080}"
