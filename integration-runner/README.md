# integration-runner

Headful Playwright runner for walking through a Stripe Checkout session created
via `mountaineer-billing`.

Usage:

```bash
export STRIPE_API_KEY=sk_test_your_key_here
docker compose up -d
uv sync --project integration-runner
uv run --project integration-runner playwright install chromium
uv run --project integration-runner integration-runner
```

The runner uses `IntegrationRunnerConfig` from `integration_runner/config.py`,
auto-creates the local schema, auto-syncs the demo catalog to Stripe test mode,
and records a video while stepping through checkout in headful Chromium. The
bundled `docker-compose.yml` exposes Postgres on `localhost:5436`, which matches
the runner's default `POSTGRES_*` settings.
