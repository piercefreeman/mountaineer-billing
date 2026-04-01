from typing import Any, ClassVar, Mapping, Sequence, Type

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
    _LEGACY_MODEL_FIELD_MAP: ClassVar[dict[str, str]] = {
        "BILLING_USER": "USER",
        "BILLING_PRODUCT_PRICE": "PRODUCT_PRICE",
        "BILLING_RESOURCE_ACCESS": "RESOURCE_ACCESS",
        "BILLING_SUBSCRIPTION": "SUBSCRIPTION",
        "BILLING_METERED_USAGE": "METERED_USAGE",
        "BILLING_PAYMENT": "PAYMENT",
        "BILLING_CHECKOUT_SESSION": "CHECKOUT_SESSION",
        "BILLING_STRIPE_EVENT": "STRIPE_EVENT",
        "BILLING_STRIPE_OBJECT": "STRIPE_OBJECT",
        "BILLING_PROJECTION_STATE": "PROJECTION_STATE",
    }

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

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_model_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized_data = dict(data)
        nested_value = data.get("BILLING_MODELS")
        if isinstance(nested_value, BillingModels):
            nested_models = nested_value.model_dump()
        elif isinstance(nested_value, dict):
            nested_models = dict(nested_value)
        else:
            nested_models = {}

        for legacy_field, nested_field in cls._LEGACY_MODEL_FIELD_MAP.items():
            if legacy_field in normalized_data and nested_field not in nested_models:
                nested_models[nested_field] = normalized_data.pop(legacy_field)

        if not nested_models:
            return normalized_data

        return {
            **normalized_data,
            "BILLING_MODELS": nested_models,
        }

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

    @property
    def BILLING_USER(self) -> Type[models.UserBillingMixin]:
        return self.BILLING_MODELS.USER

    @property
    def BILLING_PRODUCT_PRICE(self) -> Type[models.ProductPrice]:
        return self.BILLING_MODELS.PRODUCT_PRICE

    @property
    def BILLING_RESOURCE_ACCESS(self) -> Type[models.ResourceAccess]:
        return self.BILLING_MODELS.RESOURCE_ACCESS

    @property
    def BILLING_SUBSCRIPTION(self) -> Type[models.Subscription]:
        return self.BILLING_MODELS.SUBSCRIPTION

    @property
    def BILLING_METERED_USAGE(self) -> Type[models.MeteredUsage]:
        return self.BILLING_MODELS.METERED_USAGE

    @property
    def BILLING_PAYMENT(self) -> Type[models.Payment]:
        return self.BILLING_MODELS.PAYMENT

    @property
    def BILLING_CHECKOUT_SESSION(self) -> Type[models.CheckoutSession]:
        return self.BILLING_MODELS.CHECKOUT_SESSION

    @property
    def BILLING_STRIPE_EVENT(self) -> Type[models.StripeEvent]:
        return self.BILLING_MODELS.STRIPE_EVENT

    @property
    def BILLING_STRIPE_OBJECT(self) -> Type[models.StripeObject]:
        return self.BILLING_MODELS.STRIPE_OBJECT

    @property
    def BILLING_PROJECTION_STATE(self) -> Type[models.BillingProjectionState]:
        return self.BILLING_MODELS.PROJECTION_STATE
