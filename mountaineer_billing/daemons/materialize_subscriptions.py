from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from iceaxe import DBConnection, delete, select
from iceaxe.mountaineer import DatabaseDependencies
from pydantic import BaseModel, Field
from waymark import Depend, RetryPolicy, Workflow, action, workflow

from mountaineer_billing.config import BillingConfig
from mountaineer_billing.enums import StripeStatus, SyncStatus
from mountaineer_billing.stripe.types import (
    StripeCheckoutSessionPayload,
    StripeInvoicePayload,
    StripeSubscriptionPayload,
)

from .reload_stripe_object import get_billing_config, to_datetime, utcnow


@runtime_checkable
class HasStripeData(Protocol):
    data: list[Any]


@runtime_checkable
class HasStripeId(Protocol):
    id: str


@runtime_checkable
class HasStripeRoot(Protocol):
    root: str | None


def nested_stripe_id(value: object) -> str | None:
    if isinstance(value, str):
        return value

    if isinstance(value, HasStripeRoot):
        return value.root

    if isinstance(value, HasStripeId):
        return value.id

    return None


def list_data(value: HasStripeData | None) -> list[Any]:
    if value is None:
        return []

    return value.data


def subscription_items(payload: StripeSubscriptionPayload) -> list[Any]:
    if payload is None:
        return []

    return list_data(payload.items)


def checkout_line_items(payload: StripeCheckoutSessionPayload) -> list[Any]:
    if payload is None:
        return []

    return list_data(payload.line_items)


def invoice_line_items(payload: StripeInvoicePayload) -> list[Any]:
    if payload is None:
        return []

    return list_data(payload.lines)


def line_item_price_id(payload: object) -> str | None:
    price_id = nested_stripe_id(getattr(payload, "price", None)) or nested_stripe_id(
        getattr(payload, "plan", None)
    )
    if price_id:
        return price_id

    pricing = getattr(payload, "pricing", None)
    if pricing is None:
        return None

    price_details = getattr(pricing, "price_details", None)
    if price_details is None:
        return None

    return nested_stripe_id(price_details.price)


def line_item_product_id(payload: object) -> str | None:
    price = getattr(payload, "price", None)
    product_id = nested_stripe_id(getattr(price, "product", None))
    if product_id:
        return product_id

    plan = getattr(payload, "plan", None)
    product_id = nested_stripe_id(getattr(plan, "product", None))
    if product_id:
        return product_id

    pricing = getattr(payload, "pricing", None)
    if pricing is None:
        return None

    price_details = getattr(pricing, "price_details", None)
    if price_details is None:
        return None

    return nested_stripe_id(price_details.product)


def line_item_subscription_id(payload: object) -> str | None:
    subscription_id = nested_stripe_id(getattr(payload, "subscription", None))
    if subscription_id:
        return subscription_id

    parent = getattr(payload, "parent", None)
    if parent is None:
        return None

    subscription_item_details = getattr(parent, "subscription_item_details", None)
    if subscription_item_details is None:
        return None

    return nested_stripe_id(subscription_item_details.subscription)


def line_item_unit_amount(payload: object) -> int | None:
    price = getattr(payload, "price", None)
    unit_amount = getattr(price, "unit_amount", None)
    if isinstance(unit_amount, int):
        return unit_amount

    pricing = getattr(payload, "pricing", None)
    if pricing is None:
        return None

    unit_amount_decimal = getattr(pricing, "unit_amount_decimal", None)
    if isinstance(unit_amount_decimal, int):
        return unit_amount_decimal

    if isinstance(unit_amount_decimal, Decimal):
        if unit_amount_decimal == unit_amount_decimal.to_integral_value():
            return int(unit_amount_decimal)

    return None


def invoice_is_paid(payload: StripeInvoicePayload) -> bool:
    if payload is None:
        return False

    # `paid` existed on older invoice payloads, while newer versions reliably
    # expose the invoice lifecycle through `status`.
    paid = getattr(payload, "paid", None)
    if isinstance(paid, bool):
        return paid

    return payload.status == "paid"


def safe_stripe_status(value: object) -> StripeStatus | None:
    if not isinstance(value, str):
        return None
    try:
        return StripeStatus(value)
    except ValueError:
        return None


def subscription_period_start(payload: StripeSubscriptionPayload) -> datetime | None:
    if payload is None:
        return None

    # `current_period_start` exists on older subscription payloads but was removed
    # from the top-level object in newer API versions. Keep the direct access on
    # `items.data[*]`, and use `getattr` only for the version-skewed top-level field.
    direct = to_datetime(getattr(payload, "current_period_start", None))
    if direct:
        return direct

    items = subscription_items(payload)
    if items:
        return to_datetime(getattr(items[0], "current_period_start", None))

    return None


def subscription_period_end(payload: StripeSubscriptionPayload) -> datetime | None:
    if payload is None:
        return None

    # `current_period_end` has the same version split as `current_period_start`.
    direct = to_datetime(getattr(payload, "current_period_end", None))
    if direct:
        return direct

    items = subscription_items(payload)
    if items:
        return to_datetime(getattr(items[0], "current_period_end", None))

    return None


class MaterializeSubscriptionsRequest(BaseModel):
    stripe_customer_id: str
    internal_user_id: UUID | None = None


class ProductPriceReference(BaseModel):
    stripe_price_id: str
    product_id: str


class LoadMaterializationContextResponse(BaseModel):
    stripe_customer_id: str
    internal_user_id: UUID | None = None
    user_id: UUID
    checkout_sessions: list[StripeCheckoutSessionPayload] = Field(default_factory=list)
    invoices: list[StripeInvoicePayload] = Field(default_factory=list)
    subscriptions: list[StripeSubscriptionPayload] = Field(default_factory=list)
    product_prices: list[ProductPriceReference] = Field(default_factory=list)


class CheckoutSessionMaterializedRecord(BaseModel):
    stripe_checkout_session_id: str
    stripe_payment_intent_id: str | None = None
    stripe_subscription_id: str | None = None
    stripe_customer_id: str | None = None
    user_id: UUID


class SubscriptionMaterializedRecord(BaseModel):
    stripe_subscription_id: str
    stripe_status: StripeStatus | None = None
    stripe_current_period_start: datetime | None = None
    stripe_current_period_end: datetime | None = None
    stripe_checkout_session_id: str | None = None
    user_id: UUID


class ResourceAccessMaterializedRecord(BaseModel):
    started_datetime: datetime | None = None
    ended_datetime: datetime | None = None
    stripe_subscription_id: str | None = None
    is_perpetual: bool = False
    prorated_usage: float = 1.0
    stripe_price_id: str | None = None
    stripe_product_id: str | None = None
    product_id: str
    user_id: UUID


class PaymentMaterializedRecord(BaseModel):
    paid_amount: int
    total_price_amount: int
    price_ratio: float
    stripe_subscription_id: str | None = None
    stripe_customer_id: str
    stripe_price_id: str
    stripe_invoice_id: str | None = None
    user_id: UUID


class MaterializedSubscriptionState(BaseModel):
    stripe_customer_id: str
    user_id: UUID
    checkout_sessions: list[CheckoutSessionMaterializedRecord] = Field(
        default_factory=list
    )
    subscriptions: list[SubscriptionMaterializedRecord] = Field(default_factory=list)
    resource_access: list[ResourceAccessMaterializedRecord] = Field(
        default_factory=list
    )
    payments: list[PaymentMaterializedRecord] = Field(default_factory=list)


class MaterializeSubscriptionsResponse(BaseModel):
    stripe_customer_id: str
    user_id: UUID
    checkout_session_count: int = 0
    subscription_count: int = 0
    resource_access_count: int = 0
    payment_count: int = 0


@workflow
class MaterializeSubscriptions(Workflow):
    """
    Rebuild one customer's derived billing projections from the raw Stripe mirror.

    This workflow treats ``StripeObject`` as the canonical local copy of Stripe data
    and rebuilds the application-facing billing tables from scratch for a single
    Stripe customer. The goal is not to patch individual rows in place; it is to
    make the derived tables converge on the full state implied by the clean mirror.

    The workflow is intentionally customer-scoped. That keeps the action inputs
    small, makes replays predictable, and preserves the operational model implied
    by ``BillingProjectionState`` where projection work is tracked per Stripe
    customer rather than globally.

    The orchestration is split into three steps:

    1. ``load_materialization_context`` resolves the local user, verifies there are
       no non-clean raw mirror rows for that customer, and gathers the clean Stripe
       payloads plus local price mappings needed for projection.
    2. ``build_materialized_subscription_state`` derives the replacement checkout
       session, subscription, resource access, and payment rows entirely in memory.
    3. ``persist_materialized_subscription_state`` swaps the user's materialized
       tables inside one transaction and marks ``BillingProjectionState`` clean.

    This gives us a clear separation between workflow control flow, pure
    projection logic, and database writes. It also makes the daemon suitable for
    direct use after webhook processing, manual replays, or future batch drivers
    that iterate dirty customers.
    """

    async def run(  # type: ignore[override]
        self,
        *,
        stripe_customer_id: str,
        internal_user_id: UUID | None = None,
    ) -> MaterializeSubscriptionsResponse:
        context = await self.run_action(
            load_materialization_context(
                MaterializeSubscriptionsRequest(
                    stripe_customer_id=stripe_customer_id,
                    internal_user_id=internal_user_id,
                )
            ),
            retry=RetryPolicy(attempts=3, backoff_seconds=5),
            timeout=timedelta(seconds=30),
        )
        materialized_state = await self.run_action(
            build_materialized_subscription_state(context),
            retry=RetryPolicy(attempts=3, backoff_seconds=5),
            timeout=timedelta(seconds=30),
        )
        return await self.run_action(
            persist_materialized_subscription_state(materialized_state),
            retry=RetryPolicy(attempts=3, backoff_seconds=5),
            timeout=timedelta(seconds=30),
        )


@action
async def load_materialization_context(
    request: MaterializeSubscriptionsRequest,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(DatabaseDependencies.get_db_connection),  # type: ignore[assignment]
) -> LoadMaterializationContextResponse:
    """Load the clean Stripe mirror rows needed for one-customer projection."""

    stripe_object_query = select(config.BILLING_MODELS.STRIPE_OBJECT).where(
        config.BILLING_MODELS.STRIPE_OBJECT.stripe_customer_id
        == request.stripe_customer_id
    )
    stripe_objects = await db_connection.exec(stripe_object_query)

    blocking_objects = [
        stripe_object
        for stripe_object in stripe_objects
        if stripe_object.sync_status != SyncStatus.CLEAN
    ]
    if blocking_objects:
        blocking_ids = ", ".join(
            stripe_object.stripe_id for stripe_object in blocking_objects[:5]
        )
        raise ValueError(
            "Cannot materialize subscriptions while stripe objects are still dirty "
            f"for customer {request.stripe_customer_id}: {blocking_ids}"
        )

    projection_state_query = select(config.BILLING_MODELS.PROJECTION_STATE).where(
        config.BILLING_MODELS.PROJECTION_STATE.stripe_customer_id
        == request.stripe_customer_id
    )
    projection_states = await db_connection.exec(projection_state_query)
    projection_state = projection_states[0] if projection_states else None

    discovered_internal_user_id = next(
        (
            stripe_object.internal_user_id
            for stripe_object in stripe_objects
            if stripe_object.internal_user_id is not None
        ),
        None,
    )
    internal_user_id = (
        request.internal_user_id
        or (
            projection_state.internal_user_id
            if projection_state and projection_state.internal_user_id is not None
            else None
        )
        or discovered_internal_user_id
    )

    user = await find_user_for_customer(
        stripe_customer_id=request.stripe_customer_id,
        internal_user_id=internal_user_id,
        config=config,
        db_connection=db_connection,
    )
    if user is None:
        raise ValueError(
            "Could not find local user for stripe customer "
            f"{request.stripe_customer_id}"
        )

    product_prices = await db_connection.exec(
        select(config.BILLING_MODELS.PRODUCT_PRICE)
    )

    return LoadMaterializationContextResponse(
        stripe_customer_id=request.stripe_customer_id,
        internal_user_id=user.id,
        user_id=user.id,
        checkout_sessions=[
            stripe_object.checkout_session
            for stripe_object in stripe_objects
            if stripe_object.checkout_session is not None
        ],
        invoices=[
            stripe_object.invoice
            for stripe_object in stripe_objects
            if stripe_object.invoice is not None
        ],
        subscriptions=[
            stripe_object.subscription
            for stripe_object in stripe_objects
            if stripe_object.subscription is not None
        ],
        product_prices=[
            ProductPriceReference(
                stripe_price_id=product_price.stripe_price_id,
                product_id=str(product_price.product_id),
            )
            for product_price in product_prices
        ],
    )


@action
async def build_materialized_subscription_state(
    context: LoadMaterializationContextResponse,
) -> MaterializedSubscriptionState:
    """Derive the full replacement billing projection for one customer."""

    checkout_session_by_subscription: dict[str, str] = {}
    checkout_session_rows: list[CheckoutSessionMaterializedRecord] = []
    subscription_rows: list[SubscriptionMaterializedRecord] = []
    resource_rows: list[ResourceAccessMaterializedRecord] = []
    payment_rows: list[PaymentMaterializedRecord] = []
    product_prices_by_stripe_id = {
        product_price.stripe_price_id: product_price
        for product_price in context.product_prices
    }

    for payload in context.checkout_sessions:
        if payload is None:
            continue

        checkout_session_id = payload.id
        stripe_subscription_id = nested_stripe_id(payload.subscription)
        checkout_session_rows.append(
            CheckoutSessionMaterializedRecord(
                stripe_checkout_session_id=checkout_session_id,
                stripe_payment_intent_id=nested_stripe_id(payload.payment_intent),
                stripe_subscription_id=stripe_subscription_id,
                stripe_customer_id=context.stripe_customer_id,
                user_id=context.user_id,
            )
        )
        if stripe_subscription_id:
            checkout_session_by_subscription[stripe_subscription_id] = (
                checkout_session_id
            )

    for payload in context.subscriptions:
        if payload is None:
            continue

        stripe_subscription_id = payload.id
        subscription_rows.append(
            SubscriptionMaterializedRecord(
                stripe_subscription_id=stripe_subscription_id,
                stripe_status=safe_stripe_status(payload.status),
                stripe_current_period_start=subscription_period_start(payload),
                stripe_current_period_end=subscription_period_end(payload),
                stripe_checkout_session_id=checkout_session_by_subscription.get(
                    stripe_subscription_id
                ),
                user_id=context.user_id,
            )
        )

        ended_at = to_datetime(payload.ended_at)
        for item in subscription_items(payload):
            price_id = line_item_price_id(item)
            if not price_id:
                continue

            local_price = product_prices_by_stripe_id.get(price_id)
            if local_price is None:
                raise ValueError(f"Local plan not found for stripe price {price_id}")

            quantity = getattr(item, "quantity", None)
            resource_rows.append(
                ResourceAccessMaterializedRecord(
                    started_datetime=to_datetime(
                        getattr(item, "current_period_start", None)
                    )
                    or subscription_period_start(payload),
                    ended_datetime=ended_at,
                    stripe_subscription_id=stripe_subscription_id,
                    stripe_price_id=price_id,
                    stripe_product_id=line_item_product_id(item),
                    product_id=local_price.product_id,
                    prorated_usage=float(quantity or 1),
                    user_id=context.user_id,
                )
            )

    seen_payment_keys: set[tuple[str, str, str | None]] = set()
    for payload in context.invoices:
        if payload is None or not invoice_is_paid(payload):
            continue

        stripe_invoice_id = payload.id
        if not isinstance(stripe_invoice_id, str):
            continue

        # `paid` and `subscription` are not available on every invoice schema
        # version in the union, so keep those as `getattr` fallbacks.
        stripe_subscription_id = nested_stripe_id(
            getattr(payload, "subscription", None)
        )
        for line_item in invoice_line_items(payload):
            line_item_subscription = line_item_subscription_id(line_item)
            price_id = line_item_price_id(line_item)
            if not price_id:
                continue

            payment_key = ("invoice", stripe_invoice_id, price_id)
            if payment_key in seen_payment_keys:
                continue
            seen_payment_keys.add(payment_key)

            unit_amount = line_item_unit_amount(line_item)
            quantity = getattr(line_item, "quantity", None)
            if not isinstance(quantity, int) or quantity == 0:
                quantity = 1

            paid_amount = getattr(line_item, "amount", None)
            if not isinstance(paid_amount, int):
                paid_amount = payload.amount_paid
            if not isinstance(paid_amount, int):
                continue

            total_price_amount = unit_amount * quantity if unit_amount else paid_amount
            payment_rows.append(
                PaymentMaterializedRecord(
                    paid_amount=paid_amount,
                    total_price_amount=total_price_amount,
                    price_ratio=(
                        paid_amount / total_price_amount if total_price_amount else 1.0
                    ),
                    stripe_subscription_id=(
                        line_item_subscription or stripe_subscription_id
                    ),
                    stripe_customer_id=context.stripe_customer_id,
                    stripe_price_id=price_id,
                    stripe_invoice_id=stripe_invoice_id,
                    user_id=context.user_id,
                )
            )

    for payload in context.checkout_sessions:
        if payload is None or payload.payment_status != "paid":
            continue
        if nested_stripe_id(payload.subscription):
            continue

        stripe_checkout_session_id = payload.id
        stripe_invoice_id = nested_stripe_id(payload.invoice)
        for line_item in checkout_line_items(payload):
            price_id = line_item_price_id(line_item)
            if not price_id:
                continue

            local_price = product_prices_by_stripe_id.get(price_id)
            if local_price is None:
                raise ValueError(f"Local plan not found for stripe price {price_id}")

            payment_key = ("checkout", stripe_checkout_session_id, price_id)
            if payment_key not in seen_payment_keys:
                seen_payment_keys.add(payment_key)

                unit_amount = line_item_unit_amount(line_item)
                quantity = getattr(line_item, "quantity", None)
                if not isinstance(quantity, int) or quantity == 0:
                    quantity = 1

                paid_amount = getattr(line_item, "amount_subtotal", None)
                if not isinstance(paid_amount, int):
                    paid_amount = unit_amount * quantity if unit_amount else None
                if isinstance(paid_amount, int):
                    total_price_amount = (
                        unit_amount * quantity if unit_amount else paid_amount
                    )
                    payment_rows.append(
                        PaymentMaterializedRecord(
                            paid_amount=paid_amount,
                            total_price_amount=total_price_amount,
                            price_ratio=(
                                paid_amount / total_price_amount
                                if total_price_amount
                                else 1.0
                            ),
                            stripe_subscription_id=None,
                            stripe_customer_id=context.stripe_customer_id,
                            stripe_price_id=price_id,
                            stripe_invoice_id=stripe_invoice_id,
                            user_id=context.user_id,
                        )
                    )

            quantity = getattr(line_item, "quantity", None)
            resource_rows.append(
                ResourceAccessMaterializedRecord(
                    started_datetime=to_datetime(payload.created),
                    stripe_subscription_id=None,
                    is_perpetual=True,
                    prorated_usage=float(quantity or 1),
                    stripe_price_id=price_id,
                    stripe_product_id=line_item_product_id(line_item),
                    product_id=local_price.product_id,
                    user_id=context.user_id,
                )
            )

    return MaterializedSubscriptionState(
        stripe_customer_id=context.stripe_customer_id,
        user_id=context.user_id,
        checkout_sessions=checkout_session_rows,
        subscriptions=subscription_rows,
        resource_access=resource_rows,
        payments=payment_rows,
    )


@action
async def persist_materialized_subscription_state(
    state: MaterializedSubscriptionState,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(DatabaseDependencies.get_db_connection),  # type: ignore[assignment]
) -> MaterializeSubscriptionsResponse:
    """Replace the persisted billing projection with the rebuilt customer state."""

    user_rows = await db_connection.exec(
        select(config.BILLING_MODELS.USER).where(
            config.BILLING_MODELS.USER.id == state.user_id
        )
    )
    if not user_rows:
        raise ValueError(f"User {state.user_id} was not found")
    user = user_rows[0]

    if user.stripe_customer_id != state.stripe_customer_id:
        user.stripe_customer_id = state.stripe_customer_id

    now = utcnow()
    projection_state = config.BILLING_MODELS.PROJECTION_STATE(
        stripe_customer_id=state.stripe_customer_id,
        internal_user_id=state.user_id,
        projection_status=SyncStatus.CLEAN,
        dirty_since=None,
        last_projected_at=now,
        next_project_at=None,
        locked_at=None,
        retry_count=0,
        last_error=None,
        updated_at=now,
    )

    async with db_connection.transaction():
        await db_connection.update([user])
        await db_connection.exec(
            delete(config.BILLING_MODELS.RESOURCE_ACCESS).where(
                config.BILLING_MODELS.RESOURCE_ACCESS.user_id == state.user_id
            )
        )
        await db_connection.exec(
            delete(config.BILLING_MODELS.SUBSCRIPTION).where(
                config.BILLING_MODELS.SUBSCRIPTION.user_id == state.user_id
            )
        )
        await db_connection.exec(
            delete(config.BILLING_MODELS.PAYMENT).where(
                config.BILLING_MODELS.PAYMENT.user_id == state.user_id
            )
        )
        await db_connection.exec(
            delete(config.BILLING_MODELS.CHECKOUT_SESSION).where(
                config.BILLING_MODELS.CHECKOUT_SESSION.user_id == state.user_id
            )
        )

        if state.checkout_sessions:
            await db_connection.insert(
                [
                    config.BILLING_MODELS.CHECKOUT_SESSION(
                        **checkout_session.model_dump()
                    )
                    for checkout_session in state.checkout_sessions
                ]
            )
        if state.subscriptions:
            await db_connection.insert(
                [
                    config.BILLING_MODELS.SUBSCRIPTION(**subscription.model_dump())
                    for subscription in state.subscriptions
                ]
            )
        if state.resource_access:
            await db_connection.insert(
                [
                    config.BILLING_MODELS.RESOURCE_ACCESS(
                        **resource_access.model_dump()
                    )
                    for resource_access in state.resource_access
                ]
            )
        if state.payments:
            await db_connection.insert(
                [
                    config.BILLING_MODELS.PAYMENT(**payment.model_dump())
                    for payment in state.payments
                ]
            )

        await db_connection.upsert(
            [projection_state],
            conflict_fields=(
                config.BILLING_MODELS.PROJECTION_STATE.stripe_customer_id,
            ),
            update_fields=(
                config.BILLING_MODELS.PROJECTION_STATE.internal_user_id,
                config.BILLING_MODELS.PROJECTION_STATE.projection_status,
                config.BILLING_MODELS.PROJECTION_STATE.dirty_since,
                config.BILLING_MODELS.PROJECTION_STATE.last_projected_at,
                config.BILLING_MODELS.PROJECTION_STATE.next_project_at,
                config.BILLING_MODELS.PROJECTION_STATE.locked_at,
                config.BILLING_MODELS.PROJECTION_STATE.retry_count,
                config.BILLING_MODELS.PROJECTION_STATE.last_error,
                config.BILLING_MODELS.PROJECTION_STATE.updated_at,
            ),
        )

    return MaterializeSubscriptionsResponse(
        stripe_customer_id=state.stripe_customer_id,
        user_id=state.user_id,
        checkout_session_count=len(state.checkout_sessions),
        subscription_count=len(state.subscriptions),
        resource_access_count=len(state.resource_access),
        payment_count=len(state.payments),
    )


async def find_user_for_customer(
    *,
    stripe_customer_id: str,
    internal_user_id: UUID | None,
    config: BillingConfig,
    db_connection: DBConnection,
) -> Any | None:
    if internal_user_id:
        users = await db_connection.exec(
            select(config.BILLING_MODELS.USER).where(
                config.BILLING_MODELS.USER.id == internal_user_id
            )
        )
        if users:
            return users[0]

    users = await db_connection.exec(
        select(config.BILLING_MODELS.USER).where(
            config.BILLING_MODELS.USER.stripe_customer_id == stripe_customer_id
        )
    )
    return users[0] if users else None
