# integration-runner

Headful Playwright runner for walking through a Stripe Checkout session created
via `mountaineer-billing`. This will test generating a checkout, stepping through the checkout, receiving the webook events, and kicking off our backend daemon actions.

Usage:

```bash
# Set STRIPE_API_KEY in integration-runner/.env first.
docker compose up -d postgres daemon app-server
docker compose --profile stripe up stripe-cli
```

Copy the `whsec_...` signing secret printed by `stripe-cli` into
`integration-runner/.env` as `STRIPE_WEBHOOK_SECRET`, then restart `app-server`
so webhook verification uses the same secret:

```bash
docker compose restart app-server
```

Run the browser walkthrough inside the Dockerized X11 environment:

```bash
docker compose --profile runner up -d runner
docker compose exec runner /workspace/integration-runner/scripts/run-runner.sh
```

The stack now includes:

- `postgres` for the integration database on `localhost:5436`
- `daemon` for the Waymark workflow bridge and worker loop
- `app-server` for `/external/billing/webhooks/stripe` on `localhost:8000`
- `stripe-cli` for `stripe listen --forward-to ...`
- `runner` as a warmed container with Playwright and `Xvfb`, ready for `docker compose exec`

The runner will auto-sync the demo catalog to Stripe test mode, and records a video
while stepping through checkout in headful Chromium.
