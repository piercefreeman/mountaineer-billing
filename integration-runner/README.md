# integration-runner

Headful Playwright runner for walking through a Stripe Checkout session created
via `mountaineer-billing`. This will test generating a checkout, stepping through the checkout, receiving the webook events, and kicking off our backend daemon actions.

Usage:

```bash
# Set STRIPE_API_KEY in integration-runner/.env first.
./scripts/start-stripe-webhooks.sh
```

This helper starts `postgres`, `daemon`, and `app-server`, fetches the
`whsec_...` signing secret via `stripe listen --print-secret`, writes
`STRIPE_WEBHOOK_SECRET` back into `integration-runner/.env`, recreates
`app-server` so it loads the updated environment, and then attaches the live
`stripe-cli` listener.

Run the browser walkthrough inside the Dockerized X11 environment:

```bash
docker compose --profile runner up -d runner
docker compose exec runner /workspace/integration-runner/scripts/run-runner.sh
```

The stack now includes:

- `postgres` for the integration database on `localhost:5436`
- `daemon` for the Waymark workflow bridge and worker loop
- `daemon` webapp on `localhost:24119` when `WAYMARK_WEBAPP_ENABLED=true`
- `app-server` for `/external/billing/webhooks/stripe` on `localhost:8000`
- `stripe-cli` for `stripe listen --forward-to ...`
- `runner` as a warmed container with Playwright and `Xvfb`, ready for `docker compose exec`

The runner will auto-sync the demo catalog to Stripe test mode, and records a video
while stepping through checkout in headful Chromium.
