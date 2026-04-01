#!/bin/sh

set -eu

uv run --project integration-runner waymark-bridge &
bridge_pid=$!

cleanup() {
  kill "$bridge_pid" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

exec uv run --project integration-runner waymark-start-workers
