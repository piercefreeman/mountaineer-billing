"""
Billing models are intentionally split into separate layers.

Mixins:
- Shared primary-key and timestamp helpers used by the concrete tables below.

Identity and catalog:
- ``UserBillingMixin`` stores the local user fields needed to create and recover
  Stripe customers.
- ``ProductPrice`` maps stable local product/price identifiers onto Stripe price ids.

Raw Stripe mirror and workflow state:
- ``StripeEvent`` is an immutable audit log of validated webhook payloads.
- ``StripeObject`` stores the latest canonical snapshot of each Stripe object plus
  reconciliation state.
- ``BillingProjectionState`` stores customer-scoped work state for the projection
  daemon.

Derived billing projections:
- ``CheckoutSession``, ``Subscription``, ``ResourceAccess``, and ``Payment`` are
  fast-read tables built from the raw Stripe mirror.
- The application should read these tables directly.
- These tables keep Stripe ids for provenance, but they do not form a deep local
  foreign-key graph. The projection daemon can therefore rebuild them wholesale
  for a customer without having to preserve local row identities.

Local-only usage:
- ``MeteredUsage`` remains a local ledger of consumed usage. Purchased state can be
  rebuilt from Stripe, but consumed usage cannot unless it is moved to Stripe or
  another external ledger.

The intended flow is: webhook -> ``StripeEvent`` -> dirty ``StripeObject`` -> raw
reconcile daemon -> dirty ``BillingProjectionState`` -> projection daemon ->
app-facing billing tables.
"""

from datetime import date, datetime, timezone
from typing import Any, Generic, TypeVar, cast
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
from mountaineer_billing.stripe.types import (
    StripeChargePayload,
    StripeCheckoutSessionPayload,
    StripeCustomerPayload,
    StripeEventPayload,
    StripeInvoicePayload,
    StripePaymentIntentPayload,
    StripePricePayload,
    StripeProductPayload,
    StripeSubscriptionPayload,
)

ProductIDType = TypeVar("ProductIDType", bound=ProductIDBase)
PriceIDType = TypeVar("PriceIDType", bound=PriceIDBase)
MeteredIDBaseType = TypeVar("MeteredIDBaseType", bound=MeteredIDBase)
TIMESTAMPTZ = PostgresDateTime(timezone=True)
STRIPE_PAYLOAD_VERSION_FIELD = "mountaineer_billing_api_version"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def payload_with_api_version(
    payload: dict[str, Any],
    *,
    api_version: str | None,
) -> dict[str, Any]:
    if not api_version:
        raise ValueError("Stripe api_version is required for typed payload validation")

    return {
        **payload,
        STRIPE_PAYLOAD_VERSION_FIELD: api_version,
    }


#
# Mixins
#

class BillingIdentityMixin(TableBase, autodetect=False):
    id: UUID = Field(default_factory=uuid4, primary_key=True)


class CreatedAtMixin(BillingIdentityMixin, autodetect=False):
    created_at: datetime = Field(default_factory=utcnow, postgres_config=TIMESTAMPTZ)


class TimestampedMixin(CreatedAtMixin, autodetect=False):
    updated_at: datetime = Field(default_factory=utcnow, postgres_config=TIMESTAMPTZ)


#
# Identity And Catalog
#

class UserBillingMixin(BillingIdentityMixin, autodetect=False):
    """Local user fields needed for Stripe identity and checkout bootstrapping."""

    # Used to pre-seed checkout, fill out if you collect during your
    # signup process
    full_name: str | None = None

    # None until the user has gone through a purchase order flow
    stripe_customer_id: str | None = Field(default=None, unique=True)


class ProductPrice(BillingIdentityMixin, Generic[ProductIDType, PriceIDType], autodetect=False):
    """
    Local catalog mapping from stable app ids to live Stripe price ids.
    """

    product_id: ProductIDType
    price_id: PriceIDType
    frequency: PriceBillingInterval

    stripe_price_id: str = Field(unique=True)


#
# Raw Stripe Mirror And Workflow State
#

class StripeEvent(CreatedAtMixin, autodetect=False):
    """Immutable audit log of validated Stripe webhook events."""

    stripe_event_id: str = Field(unique=True)
    stripe_event_type: str
    stripe_object_id: str | None = None
    stripe_object_type: str | None = None
    stripe_customer_id: str | None = None
    livemode: bool = False
    stripe_created_at: datetime | None = Field(
        default=None,
        postgres_config=TIMESTAMPTZ,
    )
    payload: dict[str, Any] = Field(default_factory=dict, is_json=True)

    table_args = [
        IndexConstraint(columns=["stripe_object_id"]),
        IndexConstraint(columns=["stripe_customer_id"]),
    ]

    @property
    def typed_payload(self) -> "StripeEventPayload":
        from .stripe.types import StripeEventAdapter

        return cast(
            "StripeEventPayload",
            StripeEventAdapter.validate_python(
                payload_with_api_version(
                    self.payload,
                    api_version=self.payload.get("api_version"),
                )
            ),
        )


class StripeObject(TimestampedMixin, autodetect=False):
    """
    Latest canonical local snapshot of a Stripe object.

    Supported Stripe object families are stored directly in typed JSON columns keyed by
    the Stripe object family itself. Iceaxe/Pydantic handle model serialization on write
    and model reconstruction on read, so the mirror row stays simple: one object type,
    one typed payload field, plus mirror workflow metadata.

    Unsupported or not-yet-modeled Stripe objects fall back to ``generic_payload``.
    """

    stripe_id: str
    object_type: str
    livemode: bool = False
    api_version: str | None = None

    generic_payload: dict[str, Any] | None = Field(default=None, is_json=True)
    generic_payload_hash: str = ""
    charge: StripeChargePayload | None = Field(default=None, is_json=True)
    charge_hash: str = ""
    checkout_session: StripeCheckoutSessionPayload | None = Field(
        default=None,
        is_json=True,
    )
    checkout_session_hash: str = ""
    customer: StripeCustomerPayload | None = Field(default=None, is_json=True)
    customer_hash: str = ""
    invoice: StripeInvoicePayload | None = Field(default=None, is_json=True)
    invoice_hash: str = ""
    payment_intent: StripePaymentIntentPayload | None = Field(
        default=None,
        is_json=True,
    )
    payment_intent_hash: str = ""
    price: StripePricePayload | None = Field(default=None, is_json=True)
    price_hash: str = ""
    product: StripeProductPayload | None = Field(default=None, is_json=True)
    product_hash: str = ""
    subscription: StripeSubscriptionPayload | None = Field(default=None, is_json=True)
    subscription_hash: str = ""

    stripe_customer_id: str | None = None
    internal_user_id: UUID | None = None

    sync_status: SyncStatus = SyncStatus.PENDING
    dirty_since: datetime | None = Field(
        default=None,
        postgres_config=TIMESTAMPTZ,
    )
    latest_event_created_at: datetime | None = Field(
        default=None,
        postgres_config=TIMESTAMPTZ,
    )
    last_reconciled_at: datetime | None = Field(
        default=None,
        postgres_config=TIMESTAMPTZ,
    )
    next_reconcile_at: datetime | None = Field(
        default=None,
        postgres_config=TIMESTAMPTZ,
    )
    locked_at: datetime | None = Field(
        default=None,
        postgres_config=TIMESTAMPTZ,
    )
    retry_count: int = 0
    last_error: str | None = None

    remote_created_at: datetime | None = Field(
        default=None,
        postgres_config=TIMESTAMPTZ,
    )
    remote_deleted_at: datetime | None = Field(
        default=None,
        postgres_config=TIMESTAMPTZ,
    )

    table_args = [
        UniqueConstraint(columns=["stripe_id", "livemode"]),
        IndexConstraint(columns=["object_type", "sync_status"]),
        IndexConstraint(columns=["stripe_customer_id", "sync_status"]),
        IndexConstraint(columns=["next_reconcile_at"]),
    ]


class BillingProjectionState(TimestampedMixin, autodetect=False):
    """Customer-scoped work state for rebuilding derived billing projections."""

    stripe_customer_id: str = Field(unique=True)
    internal_user_id: UUID | None = None

    projection_status: SyncStatus = SyncStatus.PENDING
    dirty_since: datetime | None = Field(
        default=None,
        postgres_config=TIMESTAMPTZ,
    )
    last_projected_at: datetime | None = Field(
        default=None,
        postgres_config=TIMESTAMPTZ,
    )
    next_project_at: datetime | None = Field(
        default=None,
        postgres_config=TIMESTAMPTZ,
    )
    locked_at: datetime | None = Field(
        default=None,
        postgres_config=TIMESTAMPTZ,
    )
    retry_count: int = 0
    last_error: str | None = None

    table_args = [
        IndexConstraint(columns=["projection_status", "next_project_at"]),
    ]


#
# Derived Billing Projections
#

class CheckoutSession(BillingIdentityMixin, autodetect=False):
    """
    Derived checkout-session projection used by the application.

    This is not the raw Stripe mirror; the full Stripe payload lives in
    ``StripeObject``. This table stores only the stable fields the app queries.
    """

    stripe_checkout_session_id: str | None = Field(default=None, unique=True)
    stripe_payment_intent_id: str | None
    stripe_subscription_id: str | None
    stripe_customer_id: str | None

    user_id: UUID


class Subscription(BillingIdentityMixin, autodetect=False):
    """Derived subscription state built from raw Stripe subscription objects."""

    stripe_subscription_id: str | None = Field(default=None, unique=True)
    stripe_status: StripeStatus | None = None
    stripe_current_period_start: datetime | None = Field(
        postgres_config=TIMESTAMPTZ,
    )
    stripe_current_period_end: datetime | None = Field(
        postgres_config=TIMESTAMPTZ,
    )

    stripe_checkout_session_id: str | None = None

    user_id: UUID


class ResourceAccess(TimestampedMixin, Generic[ProductIDType], autodetect=False):
    """
    Derived entitlement rows used by the application.

    These rows are projections over Stripe subscriptions, subscription items, and
    one-time purchases. They deliberately keep Stripe ids for traceability, but the
    rows themselves are disposable and can be rebuilt from the raw mirror at any time.
    """

    # Datetime range for the actual access validity
    # If `ended_datetime` has passed, then the user no longer has access
    # to this resource
    started_datetime: datetime | None = Field(
        postgres_config=TIMESTAMPTZ,
    )
    ended_datetime: datetime | None = Field(
        default=None,
        postgres_config=TIMESTAMPTZ,
    )

    stripe_subscription_id: str | None = None
    is_perpetual: bool = False

    # If a subscription ended early, we should prorate their utilization
    prorated_usage: float = 1.0

    stripe_price_id: str | None = None
    stripe_product_id: str | None = None

    product_id: ProductIDType

    # metered_object_type: PriceBillingInterval | None

    user_id: UUID


class Payment(TimestampedMixin, autodetect=False):
    """Derived payment ledger rows used for fast billing history queries."""

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


#
# Local-Only Usage
#

class MeteredUsage(TimestampedMixin, Generic[MeteredIDBaseType], autodetect=False):
    """Local ledger of consumed usage for metered entitlements."""

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
