from datetime import date, datetime
from typing import Generic, TypeVar
from uuid import UUID, uuid4

from iceaxe import Field, PostgresDateTime, TableBase, UniqueConstraint

from mountaineer_billing.enums import PriceBillingInterval, StripeStatus
from mountaineer_billing.products import MeteredIDBase, PriceIDBase, ProductIDBase

ProductIDType = TypeVar("ProductIDType", bound=ProductIDBase)
PriceIDType = TypeVar("PriceIDType", bound=PriceIDBase)
MeteredIDBaseType = TypeVar("MeteredIDBaseType", bound=MeteredIDBase)


class UserBillingMixin(TableBase, autodetect=False):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Used to pre-seed checkout, fill out if you collect during your
    # signup process
    full_name: str | None = None

    # None until the user has gone through a purchase order flow
    stripe_customer_id: str | None = None


class ResourceAccess(TableBase, Generic[ProductIDType], autodetect=False):
    """
    ResourceAccess grants access to software.

    The simplest case perhaps is a subscription. Users pay for the subscription every
    month until they cancel. And until they do, they have a valid ResourceAccess object
    for that given resource.

    One-off purchases will simply be permanent ResourceAccess objects that don't
    have an end date. You can think of these like never-ending subscriptions.

    ResourceAccess objects are intended to be summed; if a user has multiple ResourceAccess
    objects for a given product, their specific quotas should be summed. Compare to MeteredUsage
    to determine if the user has exceeded their quota.

    Technically, this corresponds to a combination of a Subscription Item and an Invoice.

    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Attribute of the object in the local DB
    created_at: datetime = Field(
        default_factory=datetime.now,
        postgres_config=PostgresDateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        postgres_config=PostgresDateTime(timezone=True),
    )

    # Datetime range for the actual access validity
    # If `ended_datetime` has passed, then the user no longer has access
    # to this resource
    started_datetime: datetime | None = Field(
        postgres_config=PostgresDateTime(timezone=True),
    )
    ended_datetime: datetime | None = Field(
        default=None,
        postgres_config=PostgresDateTime(timezone=True),
    )

    # One of these will be true
    subscription_id: UUID | None
    is_perpetual: bool = False

    # If a subscription ended early, we should prorate their utilization
    prorated_usage: float = 1.0

    stripe_price_id: str | None
    stripe_product_id: str | None

    product_id: ProductIDType

    # metered_object_type: PriceBillingInterval | None

    user_id: UUID


class Subscription(TableBase, autodetect=False):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Only provided if this ties to an ongoing subscription
    stripe_subscription_id: str | None
    stripe_status: StripeStatus | None
    stripe_current_period_start: datetime | None = Field(
        postgres_config=PostgresDateTime(timezone=True),
    )
    stripe_current_period_end: datetime | None = Field(
        postgres_config=PostgresDateTime(timezone=True),
    )

    checkout_session_id: UUID | None = None

    user_id: UUID


class MeteredUsage(TableBase, Generic[MeteredIDBaseType], autodetect=False):
    """
    Tracks local usage for a given resource.

    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Attribute of the object in the local DB
    created_at: datetime = Field(
        default_factory=datetime.now, postgres_config=PostgresDateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, postgres_config=PostgresDateTime(timezone=True)
    )

    metered_id: MeteredIDBaseType
    metered_date: date
    metered_usage: int = 0
    synced_usage: int = 0

    is_perpetual: bool = False

    user_id: UUID

    table_args = [
        UniqueConstraint(
            columns=[
                "metered_id",
                "metered_date",
                "is_perpetual",
                "user_id",
            ]
        )
    ]


class Payment(TableBase, autodetect=False):
    """
    Confirmation of a completed payment
    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Attribute of the object in the local DB
    created_at: datetime = Field(
        default_factory=datetime.now, postgres_config=PostgresDateTime(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, postgres_config=PostgresDateTime(timezone=True)
    )

    # Stripe-specific fields
    paid_amount: int
    total_price_amount: int
    price_ratio: float

    stripe_subscription_id: str | None
    stripe_customer_id: str
    stripe_price_id: str

    # Invoice ID created by the parent checkout session, if it exists
    stripe_invoice_id: str | None

    user_id: UUID


class ProductPrice(TableBase, Generic[ProductIDType, PriceIDType], autodetect=False):
    """
    Runtime state of product prices, assigns the stripe ID.

    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    product_id: ProductIDType
    price_id: PriceIDType
    frequency: PriceBillingInterval

    stripe_price_id: str


class CheckoutSession(TableBase, autodetect=False):
    """
    Local mirror of a stripe checkout session
    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    stripe_payment_intent_id: str | None
    stripe_subscription_id: str | None
    stripe_customer_id: str | None

    user_id: UUID
