from __future__ import annotations

from iceaxe.schemas.db_memory_serializer import DatabaseMemorySerializer
from iceaxe.schemas.db_stubs import DBType

from mountaineer_auth import models as auth_models

from mountaineer_billing import models
from mountaineer_billing.products import (
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


class PriceID(PriceIDBase):
    DEFAULT = "DEFAULT"


class ProductID(ProductIDBase):
    SUBSCRIPTION_GOLD = "SUBSCRIPTION_GOLD"
    ONEOFF_50_ITEMS = "ONEOFF_50_ITEMS"


class MeteredID(MeteredIDBase):
    ITEM_GENERATION = "ITEM_GENERATION"


class User(models.UserBillingMixin, auth_models.UserAuthMixin):
    pass


class VerificationState(auth_models.VerificationState):
    pass


class ResourceAccess(models.ResourceAccess[ProductID]):
    pass


class Subscription(models.Subscription):
    pass


class MeteredUsage(models.MeteredUsage[MeteredID]):
    pass


class Payment(models.Payment):
    pass


class ProductPrice(models.ProductPrice[ProductID, PriceID]):
    pass


class CheckoutSession(models.CheckoutSession):
    pass


class StripeEvent(models.StripeEvent):
    pass


class StripeObject(models.StripeObject):
    pass


class BillingProjectionState(models.BillingProjectionState):
    pass


BILLING_PRODUCTS = [
    LicensedProduct(
        id=ProductID.SUBSCRIPTION_GOLD,
        name="Gold",
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
        id=ProductID.ONEOFF_50_ITEMS,
        name="50 Credits",
        entitlements=[
            CountDownMeteredAllocation(
                asset=MeteredID.ITEM_GENERATION,
                quantity=50,
            )
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
    )
}

RUNNER_TABLE_MODELS = [
    User,
    VerificationState,
    ProductPrice,
    ResourceAccess,
    Subscription,
    MeteredUsage,
    Payment,
    CheckoutSession,
    StripeEvent,
    StripeObject,
    BillingProjectionState,
]

RUNNER_TABLE_NAMES = frozenset(model.get_table_name() for model in RUNNER_TABLE_MODELS)
RUNNER_TYPE_NAMES = frozenset(
    obj.name
    for obj, _ in DatabaseMemorySerializer().delegate(RUNNER_TABLE_MODELS)
    if isinstance(obj, DBType)
)
