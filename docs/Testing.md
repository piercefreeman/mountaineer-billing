## Manual Tests

During manual tests, you can use Stripe's sandbox.

When testing locally you'll also want to redirect stripe events to your locally running webapp. You'll purchase through a local checkout session. This allows non-internet facing machines (your development box) to receive events from with Stripe.

To test webhooks locally we need to pair the local device with our stripe CLI.

```bash
stripe login
```

This key will expire after 90 days, at which point you'll have to reauthenticate. You'll want to listen for events at whatever API you're mounting the stripe webhook to. By default if you just mount the standard `get_billing_router` as described in these docs, you'll want to listen at the following.

```bash
stripe listen --forward-to localhost:5006/external/billing/webhooks/stripe
```
