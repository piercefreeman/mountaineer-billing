from typing import Mapping, Sequence, Type

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings

from mountaineer_billing import models
from mountaineer_billing.products import MeteredDefinition, MeteredIDBase, ProductBase


class BillingModels(BaseModel):
    USER: Type[models.UserBillingMixin] = models.UserBillingMixin
    PRODUCT_PRICE: Type[models.ProductPrice] = models.ProductPrice
    RESOURCE_ACCESS: Type[models.ResourceAccess] = models.ResourceAccess
    SUBSCRIPTION: Type[models.Subscription] = models.Subscription
    METERED_USAGE: Type[models.MeteredUsage] = models.MeteredUsage
    PAYMENT: Type[models.Payment] = models.Payment
    CHECKOUT_SESSION: Type[models.CheckoutSession] = models.CheckoutSession
    STRIPE_EVENT: Type[models.StripeEvent] = models.StripeEvent
    STRIPE_OBJECT: Type[models.StripeObject] = models.StripeObject
    PROJECTION_STATE: Type[models.BillingProjectionState] = (
        models.BillingProjectionState
    )


class BillingConfig(BaseSettings):
    STRIPE_API_KEY: str

    # Used to encrypt the webhook payload that we receive and validate
    # it came from stripe
    STRIPE_WEBHOOK_SECRET: str

    BILLING_MODELS: BillingModels = Field(default_factory=BillingModels)

    # Definition of the metadata of resources that are billed with some limits
    BILLING_METERED: Mapping[MeteredIDBase, MeteredDefinition]

    # Sequence instead of list to maintain invariance if only one subclass
    # type of product is passed
    # https://mypy.readthedocs.io/en/stable/common_issues.html#variance
    BILLING_PRODUCTS: Sequence[ProductBase]

    @model_validator(mode="after")
    def metered_ids_have_definitions(self) -> "BillingConfig":
        all_metered_ids = set(
            metered_id
            for product in self.BILLING_PRODUCTS
            for metered_id in product.get_all_metered_ids()
        )

        if all_metered_ids != set(self.BILLING_METERED):
            missing_ids = all_metered_ids - set(self.BILLING_METERED)
            additional_ids = set(self.BILLING_METERED) - all_metered_ids
            raise ValueError(
                "All metered IDs in products should have definitions in BILLING_METERED\n"
                f"Missing IDs: {missing_ids}\n"
                f"Additional IDs: {additional_ids}"
            )

        return self
