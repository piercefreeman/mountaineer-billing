#!/bin/sh

set -eu

exec xvfb-run -a -s "-screen 0 1440x1080x24" \
  uv run --project integration-runner integration-runner "$@"
