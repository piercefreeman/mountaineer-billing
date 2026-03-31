# mountaineer-billing

This plugin provides common support for webapps that need to charge for services. We support subscription-based billing, metered billing, and one-time payments. Each billing is expected to unlock some access (binary on/off) or some resources (metered). We use Stripe as the payment processor. We do not intend for this plugin to be used for the purchasing of physical goods or one-off digital goods. It fits more into a SaaS model of user linked billing.

The following data hierarchy is used by Stripe to model billing objects:

```
- Customer

- Product
    - A given offering, grants access to a specific set of resources

- Pricing (legacy name: Plan)
    - Defines the price and how it is billed
    - Could be onetime or recurring
    - Could be per month of per year
    - Links to one single product. At its core, a Price sells the same _thing_ at different pricepoints.

- Subscription (recurring access to a product)
    - Links a given pricing to a customer
    - Supports multiple prices in the subscription line-item, and therefore multiple products
```

We use a simpler hierarchy that's intended to more explicitly hook into the questions that we care about during runtime:

1. Is the user allowed to access this resource?
1. Does the user have quota remaining for this resource, for instance to create some object

## Getting started

1. Install our common daemon handlers into your daemon runner:

```python
```

## Stripe customers

We assume that every checkout session started through `mountaineer-billing` that calls out to Stripe will reference an existing stripe user. We do **not** support Stripe->Mountaineer user creation at this time.

If you're using a pricing table, for instance, this will require you to inject a customer-session-client-secret key:

```tsx
const PricingPage = (serverState: ServerState) => {
  return (
    <stripe-pricing-table
      pricing-table-id="{{PRICING_TABLE_ID}}"
      publishable-key="{{PUBLISHABLE_KEY}}"
      customer-session-client-secret={
        serverState.customer_session_client_secret
      }
    >
    </stripe-pricing-table>
  );
}
```

## Development

While running in development mode, it's often necessary to receive Stripe webhook callbacks. Their CLI makes this pretty simple. Just login and point it at your local development server:

```bash
stripe login
```

```bash
stripe listen --forward-to localhost:5006/external/billing/webhooks/stripe
```

Make sure the webhook signing secret it gives you is the same as the one speicified in your `.env` file.

While you're in test mode (and pointed to your stripe `test` environment), you should use [fake card numbers](https://docs.stripe.com/testing):

```
Card Number: 4242 4242 4242 4242
Expiration: Any future date
CVC: Any 3 digits
```

## Stripe schema generation

Stripe often bumps the version of their API to include additional data or restructure fields. Each project is versioned to a particular number and you can bump this to `latest` whenever you please. To support multiple versions of the API concurrently within `mountaineer-billing`, we compile their official OpenAPI schema into pydantic models that can be tested for cross-version compatibility. The goal is to keep our own logic the same across different versions and push the responsibility of validating this into the type definitions themselves.

Use the standalone `uv` script in `scripts/` to clone Stripe's public OpenAPI repo history, deduplicate schema revisions by `info.version`, and generate versioned Pydantic packages under `mountaineer_billing/stripe/`. For now we limit ourselves to API definitions after 2023. Ones before had quite a bit of churn.

```bash
uv run scripts/generate_stripe_models.py
```

You can also limit generation to a single Stripe API version while testing:

```bash
uv run scripts/generate_stripe_models.py --api-version 2026-03-25.dahlia
```
