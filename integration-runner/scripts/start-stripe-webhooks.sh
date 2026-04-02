#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
COMPOSE_FILE="$REPO_ROOT/integration-runner/docker-compose.yml"
ENV_FILE="$REPO_ROOT/integration-runner/.env"
FORWARD_URL="http://app-server:8000/external/billing/webhooks/stripe"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

read_env_var() {
  key="$1"
  awk -v key="$key" '
    index($0, key "=") == 1 {
      sub("^" key "=", "", $0)
      print
      exit
    }
  ' "$ENV_FILE"
}

write_env_var() {
  key="$1"
  value="$2"
  tmp_file=$(mktemp "${TMPDIR:-/tmp}/integration-runner-env.XXXXXX")
  awk -v key="$key" -v value="$value" '
    BEGIN { updated = 0 }
    index($0, key "=") == 1 {
      print key "=" value
      updated = 1
      next
    }
    { print }
    END {
      if (!updated) {
        print key "=" value
      }
    }
  ' "$ENV_FILE" > "$tmp_file"
  mv "$tmp_file" "$ENV_FILE"
}

stripe_api_key=$(read_env_var STRIPE_API_KEY)
if [ -z "${stripe_api_key:-}" ]; then
  echo "STRIPE_API_KEY is missing from $ENV_FILE" >&2
  exit 1
fi

echo "Starting integration services..."
docker compose -f "$COMPOSE_FILE" up -d --wait postgres daemon app-server

echo "Fetching Stripe webhook signing secret..."
stripe_webhook_secret=$(
  docker compose -f "$COMPOSE_FILE" run --rm --no-deps stripe-cli \
    listen \
    --api-key "$stripe_api_key" \
    --forward-to "$FORWARD_URL" \
    --print-secret \
    --skip-update | tail -n 1 | tr -d '\r'
)

case "$stripe_webhook_secret" in
  whsec_*)
    ;;
  *)
    echo "Failed to resolve Stripe webhook signing secret" >&2
    exit 1
    ;;
esac

write_env_var STRIPE_WEBHOOK_SECRET "$stripe_webhook_secret"
echo "Updated STRIPE_WEBHOOK_SECRET in $ENV_FILE"

echo "Recreating app-server so it loads the updated webhook secret..."
docker compose -f "$COMPOSE_FILE" up -d --wait --force-recreate --no-deps app-server

echo "Starting Stripe listener..."
exec docker compose -f "$COMPOSE_FILE" --profile stripe up stripe-cli
