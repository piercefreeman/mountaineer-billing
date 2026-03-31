from datetime import date, datetime
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

from iceaxe import (
    Field,
    IndexConstraint,
    PostgresDateTime,
    TableBase,
    UniqueConstraint,
)

from mountaineer_billing.enums import PriceBillingInterval, StripeStatus, SyncStatus
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
    stripe_customer_id: str | None = Field(default=None, unique=True)


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
    stripe_subscription_id: str | None = Field(default=None, unique=True)
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

    stripe_price_id: str = Field(unique=True)


class CheckoutSession(TableBase, autodetect=False):
    """
    Local mirror of a stripe checkout session
    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    stripe_checkout_session_id: str | None = Field(default=None, unique=True)
    stripe_payment_intent_id: str | None
    stripe_subscription_id: str | None
    stripe_customer_id: str | None

    user_id: UUID


class StripeEvent(TableBase, autodetect=False):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    created_at: datetime = Field(
        default_factory=datetime.now,
        postgres_config=PostgresDateTime(timezone=True),
    )

    stripe_event_id: str = Field(unique=True)
    stripe_event_type: str
    stripe_object_id: str | None = None
    stripe_object_type: str | None = None
    stripe_customer_id: str | None = None
    livemode: bool = False
    stripe_created_at: datetime | None = Field(
        default=None,
        postgres_config=PostgresDateTime(timezone=True),
    )
    payload: dict[str, Any] = Field(default_factory=dict, is_json=True)

    table_args = [
        IndexConstraint(columns=["stripe_object_id"]),
        IndexConstraint(columns=["stripe_customer_id"]),
    ]


class StripeObject(TableBase, autodetect=False):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    created_at: datetime = Field(
        default_factory=datetime.now,
        postgres_config=PostgresDateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        postgres_config=PostgresDateTime(timezone=True),
    )

    stripe_id: str
    object_type: str
    livemode: bool = False
    api_version: str | None = None

    payload: dict[str, Any] = Field(default_factory=dict, is_json=True)
    payload_hash: str = ""

    stripe_customer_id: str | None = None
    internal_user_id: UUID | None = None

    sync_status: SyncStatus = SyncStatus.PENDING
    dirty_since: datetime | None = Field(
        default=None,
        postgres_config=PostgresDateTime(timezone=True),
    )
    latest_event_created_at: datetime | None = Field(
        default=None,
        postgres_config=PostgresDateTime(timezone=True),
    )
    last_reconciled_at: datetime | None = Field(
        default=None,
        postgres_config=PostgresDateTime(timezone=True),
    )
    next_reconcile_at: datetime | None = Field(
        default=None,
        postgres_config=PostgresDateTime(timezone=True),
    )
    locked_at: datetime | None = Field(
        default=None,
        postgres_config=PostgresDateTime(timezone=True),
    )
    retry_count: int = 0
    last_error: str | None = None

    remote_created_at: datetime | None = Field(
        default=None,
        postgres_config=PostgresDateTime(timezone=True),
    )
    remote_deleted_at: datetime | None = Field(
        default=None,
        postgres_config=PostgresDateTime(timezone=True),
    )

    table_args = [
        UniqueConstraint(columns=["stripe_id", "livemode"]),
        IndexConstraint(columns=["object_type", "sync_status"]),
        IndexConstraint(columns=["stripe_customer_id", "sync_status"]),
        IndexConstraint(columns=["next_reconcile_at"]),
    ]


class BillingProjectionState(TableBase, autodetect=False):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    created_at: datetime = Field(
        default_factory=datetime.now,
        postgres_config=PostgresDateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        postgres_config=PostgresDateTime(timezone=True),
    )

    stripe_customer_id: str = Field(unique=True)
    internal_user_id: UUID | None = None

    projection_status: SyncStatus = SyncStatus.PENDING
    dirty_since: datetime | None = Field(
        default=None,
        postgres_config=PostgresDateTime(timezone=True),
    )
    last_projected_at: datetime | None = Field(
        default=None,
        postgres_config=PostgresDateTime(timezone=True),
    )
    next_project_at: datetime | None = Field(
        default=None,
        postgres_config=PostgresDateTime(timezone=True),
    )
    locked_at: datetime | None = Field(
        default=None,
        postgres_config=PostgresDateTime(timezone=True),
    )
    retry_count: int = 0
    last_error: str | None = None

    table_args = [
        IndexConstraint(columns=["projection_status", "next_project_at"]),
    ]
