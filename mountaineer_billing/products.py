"""
Classes to define in code the different products and pricing that should be
available to clients. We will sync these to Stripe to generate your products.

"""

from abc import ABC, abstractmethod
from enum import StrEnum

from pydantic import BaseModel, field_validator

from mountaineer_billing.enums import PriceBillingInterval, RollupType


class ProductIDBase(StrEnum):
    """
    For user-override with their own product offerings. Each unique product offering
    (whether one-time, billed monthly, or metered) should be defined here.

    """

    pass


class PriceIDBase(StrEnum):
    """
    Price IDs only have to be unique given a (ProductID, PriceID) pair. These are typically
    split based on different regions (if you're multi-region).

    """

    pass


class MeteredIDBase(StrEnum):
    """
    For user-override with their own metered offerings. These are
    elements that should be counted over time, where resource counts
    (# hours of compute used, # articles written, etc) makes a difference.

    """

    pass


class CountUpMeteredAllocation(BaseModel):
    asset: MeteredIDBase

    model_config = {
        "extra": "forbid",
    }


class MeteredDefinition(BaseModel):
    """
    Provides metadata that parameterizes a MeteredID

    """

    # Defines how we count the user's usage against this metered type
    usage_rollup: RollupType


class CountDownMeteredAllocation(BaseModel):
    """
    Defines the resources that the user will be allocated every month

    """

    asset: MeteredIDBase

    # The quantity of the metered resource that the user is allocated. In
    # the case of one-off purchases, these will be the total amount of
    # credits purchased.
    quantity: int

    # Determines when this quota is reset. Might be different
    # from the billing cycle; ie. if you want to reset every
    # 30 days but bill every year. Will be taken relative to
    # the user's billing cycle start date.
    # frequency: PriceBillingInterval

    model_config = {
        "extra": "forbid",
    }


class Price(BaseModel):
    """
    A static price that costs a certain amount of money at a certain interval.
    """

    # Makes it easier to establish products with only one price
    id: PriceIDBase

    # 100 = $1.00
    # For a regular LicensedProduct, this is the only price that the user will pay.
    # For a MeteredProduct, this is the price for each unit of the metered asset.
    cost: int = 0
    currency: str = "USD"
    frequency: PriceBillingInterval

    model_config = {
        "extra": "forbid",
    }


class ProductBase(BaseModel, ABC):
    # Internal ID; you should only have one product specification
    # per declared ID enum value
    id: ProductIDBase

    # Human readable name, displayed on the store
    name: str

    prices: list[Price] = []

    # A list of features that are included with this product, used for pricing
    # pages if generated automatically
    marketing_features: list[str] = []

    @field_validator("marketing_features")
    def validate_marketing_features(cls, value: list[str]):
        # Each feature must be under 80 characters
        if any(len(feature) > 80 for feature in value):
            raise ValueError("Each feature must be under 80 characters")

        # Maximum of 15 features
        if len(value) > 15:
            raise ValueError("Maximum of 15 features are allowed")

        return value

    model_config = {
        "extra": "forbid",
    }

    @abstractmethod
    def get_all_metered_ids(self) -> set[MeteredIDBase]:
        pass


class LicensedProduct(ProductBase):
    """
    A product with an upfront cost.
    """

    # If this product grants access to a certain set of metered assets,
    # list them here
    entitlements: list[CountDownMeteredAllocation] = []

    def get_all_metered_ids(self):
        return {entitlement.asset for entitlement in self.entitlements}


class MeteredProduct(ProductBase):
    """
    A product with no upfront cost, but bills based on usage.
    """

    # Start at 0, bill up as the user uses the metered asset
    # We assume that all prices for this product are linked to this
    # given metered type
    entitlement: CountUpMeteredAllocation

    def get_all_metered_ids(self) -> set[MeteredIDBase]:
        return {self.entitlement.asset}
