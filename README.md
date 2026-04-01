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

# User additions
class User(billing_models.UserBillingMixin, auth_models.UserAuthMixin, TableBase): ...

# Regular table additions
class VerificationState(auth_models.VerificationState, TableBase): ...
class ProductPrice(billing_models.ProductPrice[ProductID, PriceID], TableBase): ...
class ResourceAccess(billing_models.ResourceAccess[ProductID], TableBase): ...
class Subscription(billing_models.Subscription, TableBase): ...
class MeteredUsage(billing_models.MeteredUsage[MeteredID], TableBase): ...
class Payment(billing_models.Payment, TableBase): ...
class CheckoutSession(billing_models.CheckoutSession, TableBase): ...
class StripeEvent(billing_models.StripeEvent, TableBase): ...
class StripeObject(billing_models.StripeObject, TableBase): ...
class BillingProjectionState(billing_models.BillingProjectionState, TableBase): ...
```

4. Compose your app config and point `BillingConfig` at those concrete types:

```python
from iceaxe.mountaineer import DatabaseConfig
from mountaineer import ConfigBase
from mountaineer_auth import AuthConfig

from mountaineer_billing import BillingConfig, BillingModels, models as billing_models


class AppConfig(ConfigBase, AuthConfig, BillingConfig, DatabaseConfig):
    STRIPE_API_KEY: str
    STRIPE_WEBHOOK_SECRET: str

    BILLING_MODELS: BillingModels = BillingModels(
        USER=User,
        PRODUCT_PRICE=ProductPrice,
        RESOURCE_ACCESS=ResourceAccess,
        SUBSCRIPTION=Subscription,
        METERED_USAGE=MeteredUsage,
        PAYMENT=Payment,
        CHECKOUT_SESSION=CheckoutSession,
        STRIPE_EVENT=StripeEvent,
        STRIPE_OBJECT=StripeObject,
        PROJECTION_STATE=BillingProjectionState,
    )

    BILLING_PRODUCTS = BILLING_PRODUCTS
    BILLING_METERED = BILLING_METERED
```

5. Mount the webhook router:

```python
from mountaineer_billing.webhook import router as billing_router

controller.app.include_router(billing_router)
```

After that:

- Include these tables in your normal Iceaxe `createdb` / migration flow.
- Use the built-in `billing-sync` CLI.
- In Stripe, configure a webhook for
  `/external/billing/webhooks/stripe` and set the resulting signing secret as
  `STRIPE_WEBHOOK_SECRET`.

6. Sync your billing catalog and local Stripe mirror:

```bash
# Preview catalog changes without writing to Stripe
billing-sync up --config your_app.config:AppConfig --dry-run

# Push local BILLING_PRODUCTS into Stripe and upsert local price mappings
billing-sync up --config your_app.config:AppConfig

# Mirror supported Stripe objects back into the local StripeObject table
billing-sync down --config your_app.config:AppConfig

# Rebuild local billing projections for all users with a Stripe customer id
stripe-sync materialize --config your_app.config:AppConfig
```

If you prefer not to repeat the config path each time, set
`MOUNTAINEER_BILLING_CONFIG`:

```bash
export MOUNTAINEER_BILLING_CONFIG=your_app.config:AppConfig

billing-sync up --dry-run
billing-sync up
billing-sync down
stripe-sync materialize
```

## Using Billing

Once your catalog is synced and Stripe is sending webhooks to
`/external/billing/webhooks/stripe`, you can treat billing as a local runtime
problem instead of a Stripe API problem.

The usual flow looks like this:

1. Start checkout for a plan or one-time pack.
2. Let the webhook pipeline materialize the user's local billing state.
3. Read local billing projections to decide what the user can access.
4. Gate metered actions with `verify_capacity(...)`.
5. Record successful usage with `record_metered_usage(...)`.

Here are some examples of common validations you'll want to run after the user has started their subscription.

### Start the checkout flow

`BillingDependencies.checkout_builder` returns a helper that creates a Stripe
checkout session for one or more `(product_id, price_id)` pairs from your local
catalog.

```python
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends
from mountaineer_billing import BillingDependencies
from pydantic import BaseModel

from myapp.enums import PriceID, ProductID

router = APIRouter()


class StartCheckoutRequest(BaseModel):
    product_id: ProductID
    price_id: PriceID = PriceID.DEFAULT


@router.post("/billing/checkout")
async def start_checkout(
    request: StartCheckoutRequest,
    build_checkout: Callable[..., Awaitable[str]] = Depends(
        BillingDependencies.checkout_builder
    ),
) -> dict[str, str]:
    checkout_url = await build_checkout(
        products=[(request.product_id, request.price_id)],
        success_url="https://myapp.com/billing/success",
        cancel_url="https://myapp.com/billing",
        allow_promotion_codes=True,
    )
    return {"checkout_url": checkout_url}
```

If the current user does not yet have a `stripe_customer_id`,
`checkout_builder` will create the Stripe customer before it creates the
checkout session.

### Read local billing state

Most product code needs to verify users against the version of their subscription that they have, which lets you
gate features behind their plan.

```python
from mountaineer import Depends
from mountaineer_billing import BillingDependencies, ResourceAccess, Subscription

from myapp.enums import ProductID


async def billing_summary(
    resources: list[ResourceAccess] = Depends(BillingDependencies.get_user_resources),
    subscription: Subscription | None = Depends(
        BillingDependencies.any_subscription
    ),
) -> dict[str, bool]:
    has_pro = any(resource.product_id == ProductID.PRO for resource in resources)

    return {
        "has_pro": has_pro,
        "has_subscription": subscription is not None,
    }
```

### Gate and bill metered actions

For authenticated actions that consume quota, the normal pattern is:

1. Reject the request if the user is already out of capacity.
2. Record the usage as part of the same action.
3. Let the dependency roll back the usage record if the action body fails. This will happen automatically if you use the record_metered_usage helper.

```python
from mountaineer import Depends
from mountaineer_billing import BillingDependencies
from pydantic import BaseModel
from waymark import action

from myapp.enums import MeteredID


class GenerateItemRequest(BaseModel):
    prompt: str


@action
async def generate_item(
    request: GenerateItemRequest,
    _: bool = Depends(
        BillingDependencies.verify_capacity(
            MeteredID.ITEM_GENERATION,
            1,
        )
    ),
    __: bool = Depends(
        BillingDependencies.record_metered_usage(
            MeteredID.ITEM_GENERATION,
            1,
        )
    ),
) -> str:
    return await actually_generate_item(request.prompt)
```

### Bill a specific user from a worker or daemon

Sometimes the action that should consume quota runs outside the current request
context. In that case, fetch the user yourself and evaluate the billing
dependencies with `get_function_dependencies(...)`.

```python
from uuid import UUID

from iceaxe import DBConnection, select
from iceaxe.mountaineer import DatabaseDependencies
from mountaineer import CoreDependencies, Depends, dependency_override
from mountaineer_auth import AuthDependencies
from mountaineer_billing import BillingDependencies, UserBillingMixin
from pydantic import BaseModel
from waymark import action

from myapp.config import AppConfig
from myapp.enums import MeteredID


class BillForMeteredTypeRequest(BaseModel):
    user_id: UUID
    metered_id: MeteredID
    bill_amount: int = 1


async def get_user_from_metered_request(
    request: BillForMeteredTypeRequest,
    db_connection: DBConnection = Depends(DatabaseDependencies.get_db_connection),
    config: AppConfig = Depends(CoreDependencies.get_config_with_type(AppConfig)),
) -> UserBillingMixin:
    users = await db_connection.exec(
        select(config.BILLING_MODELS.USER).where(
            config.BILLING_MODELS.USER.id == request.user_id
        )
    )
    user = users[0] if users else None
    if not user:
        raise ValueError(f"Could not find user {request.user_id}")
    return user


@action
@dependency_override(
    AuthDependencies.require_valid_user,
    get_user_from_metered_request,
)
async def bill_for_metered_type(
    request: BillForMeteredTypeRequest,
    allocate_new_capacity: bool = Depends(
        BillingDependencies.record_metered_usage(
            request.metered_id,
            request.bill_amount,
        )
    ),
) -> bool:
    return allocate_new_capacity
```

We recommend a dedicated action for this kind of billing side effect because it
keeps retries explicit and separates "do the work" from "charge quota for the
work".

### Use hosted pricing tables or buy buttons

Every checkout flow in `mountaineer-billing` assumes you already have a local
user and want to attach Stripe billing to that user. If you're using Stripe
pricing tables or buy buttons, inject a customer session client secret with
`BillingDependencies.customer_session_authorization(...)`:

```python
from mountaineer import Depends
from mountaineer_billing import BillingDependencies


async def render_pricing_page(
    customer_session_client_secret: str = Depends(
        BillingDependencies.customer_session_authorization(["pricing_table"])
    ),
):
    return {
        "customer_session_client_secret": customer_session_client_secret,
    }
```

Then pass that secret into the frontend component:

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

## Testing Your Checkout

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

## Development

If you're looking to improve `mountaineer-billing`, clone it locally and explore the Makefile.

### Stripe schema generation

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
