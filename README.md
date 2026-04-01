# mountaineer-billing

This plugin provides common support for webapps that need to charge for services.

## Getting Started

Your app owns the concrete database tables and config, while
`mountaineer-billing` provides mixins, dependencies, webhooks, and Stripe sync
logic. The examples below assume you are already using `mountaineer`,
`iceaxe`, and `mountaineer-auth`.

1. Install the package:

```bash
uv add mountaineer-billing
```

2. Define your billing ids and local product catalog:

```python
from mountaineer_billing import (
    CountDownMeteredAllocation,
    LicensedProduct,
    MeteredDefinition,
    MeteredIDBase,
    Price,
    PriceBillingInterval,
    PriceIDBase,
    ProductIDBase,
    RollupType,
)


class ProductID(ProductIDBase):
    PRO = "PRO"
    CREDIT_PACK = "CREDIT_PACK"


class PriceID(PriceIDBase):
    DEFAULT = "DEFAULT"


class MeteredID(MeteredIDBase):
    ITEM_GENERATION = "ITEM_GENERATION"


BILLING_PRODUCTS = [
    LicensedProduct(
        id=ProductID.PRO,
        name="Pro",
        entitlements=[
            CountDownMeteredAllocation(
                asset=MeteredID.ITEM_GENERATION,
                quantity=20,
            ),
        ],
        prices=[
            Price(
                id=PriceID.DEFAULT,
                cost=2999,
                frequency=PriceBillingInterval.MONTH,
            )
        ],
    ),
    LicensedProduct(
        id=ProductID.CREDIT_PACK,
        name="50 Credits",
        entitlements=[
            CountDownMeteredAllocation(
                asset=MeteredID.ITEM_GENERATION,
                quantity=50,
            ),
        ],
        prices=[
            Price(
                id=PriceID.DEFAULT,
                cost=1999,
                frequency=PriceBillingInterval.ONETIME,
            )
        ],
    ),
]

BILLING_METERED: dict[MeteredIDBase, MeteredDefinition] = {
    MeteredID.ITEM_GENERATION: MeteredDefinition(
        usage_rollup=RollupType.AGGREGATE,
    ),
}
```

3. Add concrete billing tables to your app. Your user model should mix in
   `UserBillingMixin`, and you should subclass each billing table so Iceaxe can
   manage them in your normal migration flow:

```python
from iceaxe import TableBase
from mountaineer_auth import models as auth_models

from mountaineer_billing import models as billing_models


class User(billing_models.UserBillingMixin, auth_models.UserAuthMixin, TableBase):
    pass


class VerificationState(auth_models.VerificationState, TableBase):
    pass


class ProductPrice(
    billing_models.ProductPrice[ProductID, PriceID],
    TableBase,
):
    pass


class ResourceAccess(billing_models.ResourceAccess[ProductID], TableBase):
    pass


class Subscription(billing_models.Subscription, TableBase):
    pass


class MeteredUsage(billing_models.MeteredUsage[MeteredID], TableBase):
    pass


class Payment(billing_models.Payment, TableBase):
    pass


class CheckoutSession(billing_models.CheckoutSession, TableBase):
    pass


class StripeEvent(billing_models.StripeEvent, TableBase):
    pass


class StripeObject(billing_models.StripeObject, TableBase):
    pass


class BillingProjectionState(
    billing_models.BillingProjectionState,
    TableBase,
):
    pass
```

4. Compose your app config and point `BillingConfig` at those concrete types:

```python
from iceaxe.mountaineer import DatabaseConfig
from mountaineer import ConfigBase
from mountaineer_auth import AuthConfig

from mountaineer_billing import BillingConfig, models as billing_models


class AppConfig(ConfigBase, AuthConfig, BillingConfig, DatabaseConfig):
    STRIPE_API_KEY: str
    STRIPE_WEBHOOK_SECRET: str

    BILLING_USER: type[billing_models.UserBillingMixin] = User
    BILLING_PRODUCT_PRICE: type[billing_models.ProductPrice] = ProductPrice
    BILLING_RESOURCE_ACCESS: type[billing_models.ResourceAccess] = ResourceAccess
    BILLING_SUBSCRIPTION: type[billing_models.Subscription] = Subscription
    BILLING_METERED_USAGE: type[billing_models.MeteredUsage] = MeteredUsage
    BILLING_PAYMENT: type[billing_models.Payment] = Payment
    BILLING_CHECKOUT_SESSION: type[billing_models.CheckoutSession] = CheckoutSession
    BILLING_STRIPE_EVENT: type[billing_models.StripeEvent] = StripeEvent
    BILLING_STRIPE_OBJECT: type[billing_models.StripeObject] = StripeObject
    BILLING_PROJECTION_STATE: type[billing_models.BillingProjectionState] = (
        BillingProjectionState
    )

    BILLING_PRODUCTS = BILLING_PRODUCTS
    BILLING_METERED = BILLING_METERED
```

5. Mount the webhook router:

```python
from mountaineer_billing import get_billing_router

controller.app.include_router(get_billing_router())
```

After that:

- Include these tables in your normal Iceaxe `createdb` / migration flow.
- Use the built-in `billing-sync` CLI.
- In Stripe, configure a webhook for
  `/external/billing/webhooks/stripe` and set the resulting signing secret as
  `STRIPE_WEBHOOK_SECRET`.

Call the CLI with your application config import path:

```bash
# Preview catalog changes without writing to Stripe
billing-sync up --config your_app.config:AppConfig --dry-run

# Push local BILLING_PRODUCTS into Stripe and upsert local price mappings
billing-sync up --config your_app.config:AppConfig

# Mirror supported Stripe objects back into the local StripeObject table
billing-sync down --config your_app.config:AppConfig
```

If you prefer not to repeat the config path each time, set
`MOUNTAINEER_BILLING_CONFIG`:

```bash
export MOUNTAINEER_BILLING_CONFIG=your_app.config:AppConfig

billing-sync up --dry-run
billing-sync up
billing-sync down
```

At runtime, use `BillingDependencies` in your routes and Waymark actions for
common operations like `verify_capacity`, `record_metered_usage`,
`checkout_builder`, and `customer_session_authorization`.

## Design Details

We support subscription-based billing, metered billing, and one-time payments. Each billing is expected to unlock some access (binary on/off) or some resources (metered). We use Stripe as the payment processor. We do not intend for this plugin to be used for the purchasing of physical goods or one-off digital goods. It fits more into a SaaS model of user linked billing.

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

See [docs/StripeTypes.md](docs/StripeTypes.md) for the rationale behind the generated typing layer, including why static type checking sees all Stripe versions while runtime validation stays lazy, and why we prune Stripe's full OpenAPI schema down to the object families we actually use.

```bash
uv run scripts/generate_stripe_models.py
```

You can also limit generation to a single Stripe API version while testing:

```bash
uv run scripts/generate_stripe_models.py --api-version 2026-03-25.dahlia
```

If you are regenerating repeatedly against an existing local checkout, skip the `git fetch` step:

```bash
uv run scripts/generate_stripe_models.py --no-fetch
```
