from __future__ import annotations

import json
import warnings
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
from uuid import UUID

import asyncpg
import stripe
from iceaxe import DBConnection, or_, select
from iceaxe.mountaineer import DatabaseConfig

from mountaineer.dependencies import CoreDependencies

from mountaineer_billing import models
from mountaineer_billing.config import BillingConfig
from mountaineer_billing.dependencies.stripe import INTERNAL_USER_ID_KEY
from mountaineer_billing.enums import StripeStatus, SyncStatus
from mountaineer_billing.logging import LOGGER
from mountaineer_billing.stripe.types import (
    StripeChargeAdapter,
    StripeCheckoutSessionAdapter,
    StripeCustomerAdapter,
    StripeInvoiceAdapter,
    StripePaymentIntentAdapter,
    StripePriceAdapter,
    StripeProductAdapter,
    StripeSubscriptionAdapter,
)

SUPPORTED_OBJECT_TYPES = {
    "charge",
    "checkout.session",
    "customer",
    "invoice",
    "payment_intent",
    "price",
    "product",
    "subscription",
}


def get_billing_config() -> BillingConfig:
    return CoreDependencies.get_config_with_type(BillingConfig)()


def get_database_config() -> DatabaseConfig:
    return CoreDependencies.get_config_with_type(DatabaseConfig)()


async def get_db_connection():
    config = get_database_config()
    conn = await asyncpg.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
        database=config.POSTGRES_DB,
    )
    try:
        yield DBConnection(conn)
    finally:
        await conn.close()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def stripe_object_to_dict(stripe_object: Any) -> dict[str, Any]:
    if isinstance(stripe_object, dict):
        return stripe_object

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        if hasattr(stripe_object, "to_dict_recursive"):
            return stripe_object.to_dict_recursive()

    raise ValueError(f"Cannot serialize stripe object: {stripe_object!r}")


def payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return sha256(encoded).hexdigest()


def nested_id(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        raw_id = value.get("id")
        return raw_id if isinstance(raw_id, str) else None
    return None


def get_metadata(payload: dict[str, Any]) -> dict[str, str]:
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        return {str(key): str(value) for key, value in metadata.items()}
    return {}


def extract_customer_id(payload: dict[str, Any]) -> str | None:
    object_type = payload.get("object")
    if object_type == "customer":
        customer_id = payload.get("id")
        return customer_id if isinstance(customer_id, str) else None

    customer_value = payload.get("customer")
    customer_id = nested_id(customer_value)
    if customer_id:
        return customer_id

    return None


def extract_internal_user_id(payload: dict[str, Any]) -> UUID | None:
    metadata_value = get_metadata(payload).get(INTERNAL_USER_ID_KEY)
    if metadata_value:
        try:
            return UUID(metadata_value)
        except ValueError:
            LOGGER.warning("Invalid internal user id in metadata: %s", metadata_value)

    if payload.get("object") == "checkout.session":
        client_reference_id = payload.get("client_reference_id")
        if isinstance(client_reference_id, str):
            try:
                return UUID(client_reference_id)
            except ValueError:
                LOGGER.warning(
                    "Invalid checkout client_reference_id: %s",
                    client_reference_id,
                )

    customer = payload.get("customer")
    if isinstance(customer, dict):
        return extract_internal_user_id(customer)

    return None


def extract_primary_object(
    event_payload: dict[str, Any],
) -> tuple[str | None, str | None, dict[str, Any] | None]:
    data = event_payload.get("data")
    if not isinstance(data, dict):
        return None, None, None
    obj = data.get("object")
    if not isinstance(obj, dict):
        return None, None, None

    stripe_id = obj.get("id")
    object_type = obj.get("object")
    if not isinstance(stripe_id, str) or not isinstance(object_type, str):
        return None, None, None

    return stripe_id, object_type, obj


def supported_child_objects(payload: Any) -> dict[tuple[str, str], dict[str, Any]]:
    collected: dict[tuple[str, str], dict[str, Any]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            object_type = value.get("object")
            object_id = value.get("id")
            if (
                isinstance(object_type, str)
                and isinstance(object_id, str)
                and object_type in SUPPORTED_OBJECT_TYPES
            ):
                collected[(object_type, object_id)] = value

            for nested_value in value.values():
                visit(nested_value)
        elif isinstance(value, list):
            for nested_value in value:
                visit(nested_value)

    visit(payload)
    return collected


def next_retry_time(retry_count: int) -> datetime:
    delay_seconds = min(300, max(5, 2**retry_count))
    return utcnow() + timedelta(seconds=delay_seconds)


def subscription_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items")
    if isinstance(items, dict):
        data = items.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


def checkout_line_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    line_items = payload.get("line_items")
    if isinstance(line_items, dict):
        data = line_items.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


def invoice_line_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    lines = payload.get("lines")
    if isinstance(lines, dict):
        data = lines.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    return []


def line_item_price_id(payload: dict[str, Any]) -> str | None:
    return nested_id(payload.get("price")) or nested_id(payload.get("plan"))


def line_item_product_id(payload: dict[str, Any]) -> str | None:
    price = payload.get("price")
    if isinstance(price, dict):
        return nested_id(price.get("product"))

    plan = payload.get("plan")
    if isinstance(plan, dict):
        return nested_id(plan.get("product"))

    return None


def safe_stripe_status(value: Any) -> StripeStatus | None:
    if not isinstance(value, str):
        return None
    try:
        return StripeStatus(value)
    except ValueError:
        return None


def subscription_period_start(payload: dict[str, Any]) -> datetime | None:
    direct = to_datetime(payload.get("current_period_start"))
    if direct:
        return direct
    items = subscription_items(payload)
    if items:
        return to_datetime(items[0].get("current_period_start"))
    return None


def subscription_period_end(payload: dict[str, Any]) -> datetime | None:
    direct = to_datetime(payload.get("current_period_end"))
    if direct:
        return direct
    items = subscription_items(payload)
    if items:
        return to_datetime(items[0].get("current_period_end"))
    return None


async def upsert_projection_state(
    *,
    stripe_customer_id: str,
    internal_user_id: UUID | None,
    db_connection: DBConnection,
    config: BillingConfig,
) -> None:
    now = utcnow()
    projection_state = config.BILLING_PROJECTION_STATE(
        stripe_customer_id=stripe_customer_id,
        internal_user_id=internal_user_id,
        projection_status=SyncStatus.PENDING,
        dirty_since=now,
        next_project_at=now,
        locked_at=None,
        last_error=None,
        updated_at=now,
    )
    await db_connection.upsert(
        [projection_state],
        conflict_fields=(config.BILLING_PROJECTION_STATE.stripe_customer_id,),
        update_fields=(
            config.BILLING_PROJECTION_STATE.internal_user_id,
            config.BILLING_PROJECTION_STATE.projection_status,
            config.BILLING_PROJECTION_STATE.dirty_since,
            config.BILLING_PROJECTION_STATE.next_project_at,
            config.BILLING_PROJECTION_STATE.locked_at,
            config.BILLING_PROJECTION_STATE.last_error,
            config.BILLING_PROJECTION_STATE.updated_at,
        ),
    )


async def upsert_stripe_object(
    *,
    stripe_id: str,
    object_type: str,
    livemode: bool,
    payload: dict[str, Any],
    sync_status: SyncStatus,
    db_connection: DBConnection,
    config: BillingConfig,
    api_version: str | None = None,
    latest_event_created_at: datetime | None = None,
    dirty_since: datetime | None = None,
    next_reconcile_at: datetime | None = None,
    last_reconciled_at: datetime | None = None,
    retry_count: int = 0,
    locked_at: datetime | None = None,
    last_error: str | None = None,
) -> None:
    now = utcnow()
    payload_digest = payload_hash(payload)
    stripe_object = config.BILLING_STRIPE_OBJECT(
        stripe_id=stripe_id,
        object_type=object_type,
        livemode=livemode,
        api_version=api_version,
        generic_payload=payload if object_type not in SUPPORTED_OBJECT_TYPES else None,
        generic_payload_hash=payload_digest if object_type not in SUPPORTED_OBJECT_TYPES else "",
        charge=(
            StripeChargeAdapter.validate_python(payload, api_version=api_version)
            if object_type == "charge"
            else None
        ),
        charge_hash=payload_digest if object_type == "charge" else "",
        checkout_session=(
            StripeCheckoutSessionAdapter.validate_python(payload, api_version=api_version)
            if object_type == "checkout.session"
            else None
        ),
        checkout_session_hash=payload_digest if object_type == "checkout.session" else "",
        customer=(
            StripeCustomerAdapter.validate_python(payload, api_version=api_version)
            if object_type == "customer"
            else None
        ),
        customer_hash=payload_digest if object_type == "customer" else "",
        invoice=(
            StripeInvoiceAdapter.validate_python(payload, api_version=api_version)
            if object_type == "invoice"
            else None
        ),
        invoice_hash=payload_digest if object_type == "invoice" else "",
        payment_intent=(
            StripePaymentIntentAdapter.validate_python(payload, api_version=api_version)
            if object_type == "payment_intent"
            else None
        ),
        payment_intent_hash=payload_digest if object_type == "payment_intent" else "",
        price=(
            StripePriceAdapter.validate_python(payload, api_version=api_version)
            if object_type == "price"
            else None
        ),
        price_hash=payload_digest if object_type == "price" else "",
        product=(
            StripeProductAdapter.validate_python(payload, api_version=api_version)
            if object_type == "product"
            else None
        ),
        product_hash=payload_digest if object_type == "product" else "",
        subscription=(
            StripeSubscriptionAdapter.validate_python(payload, api_version=api_version)
            if object_type == "subscription"
            else None
        ),
        subscription_hash=payload_digest if object_type == "subscription" else "",
        stripe_customer_id=extract_customer_id(payload),
        internal_user_id=extract_internal_user_id(payload),
        sync_status=sync_status,
        dirty_since=dirty_since,
        latest_event_created_at=latest_event_created_at,
        last_reconciled_at=last_reconciled_at,
        next_reconcile_at=next_reconcile_at,
        locked_at=locked_at,
        retry_count=retry_count,
        last_error=last_error,
        remote_created_at=to_datetime(payload.get("created")),
        remote_deleted_at=now if payload.get("deleted") else None,
        updated_at=now,
    )
    await db_connection.upsert(
        [stripe_object],
        conflict_fields=(
            config.BILLING_STRIPE_OBJECT.stripe_id,
            config.BILLING_STRIPE_OBJECT.livemode,
        ),
        update_fields=(
            config.BILLING_STRIPE_OBJECT.object_type,
            config.BILLING_STRIPE_OBJECT.api_version,
            config.BILLING_STRIPE_OBJECT.generic_payload,
            config.BILLING_STRIPE_OBJECT.generic_payload_hash,
            config.BILLING_STRIPE_OBJECT.charge,
            config.BILLING_STRIPE_OBJECT.charge_hash,
            config.BILLING_STRIPE_OBJECT.checkout_session,
            config.BILLING_STRIPE_OBJECT.checkout_session_hash,
            config.BILLING_STRIPE_OBJECT.customer,
            config.BILLING_STRIPE_OBJECT.customer_hash,
            config.BILLING_STRIPE_OBJECT.invoice,
            config.BILLING_STRIPE_OBJECT.invoice_hash,
            config.BILLING_STRIPE_OBJECT.payment_intent,
            config.BILLING_STRIPE_OBJECT.payment_intent_hash,
            config.BILLING_STRIPE_OBJECT.price,
            config.BILLING_STRIPE_OBJECT.price_hash,
            config.BILLING_STRIPE_OBJECT.product,
            config.BILLING_STRIPE_OBJECT.product_hash,
            config.BILLING_STRIPE_OBJECT.subscription,
            config.BILLING_STRIPE_OBJECT.subscription_hash,
            config.BILLING_STRIPE_OBJECT.stripe_customer_id,
            config.BILLING_STRIPE_OBJECT.internal_user_id,
            config.BILLING_STRIPE_OBJECT.sync_status,
            config.BILLING_STRIPE_OBJECT.dirty_since,
            config.BILLING_STRIPE_OBJECT.latest_event_created_at,
            config.BILLING_STRIPE_OBJECT.last_reconciled_at,
            config.BILLING_STRIPE_OBJECT.next_reconcile_at,
            config.BILLING_STRIPE_OBJECT.locked_at,
            config.BILLING_STRIPE_OBJECT.retry_count,
            config.BILLING_STRIPE_OBJECT.last_error,
            config.BILLING_STRIPE_OBJECT.remote_created_at,
            config.BILLING_STRIPE_OBJECT.remote_deleted_at,
            config.BILLING_STRIPE_OBJECT.updated_at,
        ),
    )


async def claim_reconcile_batch(
    *,
    limit: int,
    db_connection: DBConnection,
    config: BillingConfig,
) -> list[models.StripeObject]:
    now = utcnow()
    stale_lock = now - timedelta(minutes=5)

    async with db_connection.transaction():
        query = (
            select(config.BILLING_STRIPE_OBJECT)
            .where(
                or_(
                    config.BILLING_STRIPE_OBJECT.sync_status == SyncStatus.PENDING,
                    config.BILLING_STRIPE_OBJECT.sync_status == SyncStatus.FAILED,
                )
            )
            .where(
                or_(
                    config.BILLING_STRIPE_OBJECT.next_reconcile_at == None,  # noqa: E711
                    config.BILLING_STRIPE_OBJECT.next_reconcile_at <= now,
                )
            )
            .where(
                or_(
                    config.BILLING_STRIPE_OBJECT.locked_at == None,  # noqa: E711
                    config.BILLING_STRIPE_OBJECT.locked_at < stale_lock,
                )
            )
            .order_by(config.BILLING_STRIPE_OBJECT.dirty_since, "ASC")
            .limit(limit)
            .for_update(skip_locked=True)
        )
        rows = await db_connection.exec(query)
        for row in rows:
            row.sync_status = SyncStatus.SYNCING
            row.locked_at = now
            row.updated_at = now
        await db_connection.update(rows)
        return rows


async def claim_projection_batch(
    *,
    limit: int,
    db_connection: DBConnection,
    config: BillingConfig,
) -> list[models.BillingProjectionState]:
    now = utcnow()
    stale_lock = now - timedelta(minutes=5)

    async with db_connection.transaction():
        query = (
            select(config.BILLING_PROJECTION_STATE)
            .where(
                or_(
                    config.BILLING_PROJECTION_STATE.projection_status
                    == SyncStatus.PENDING,
                    config.BILLING_PROJECTION_STATE.projection_status
                    == SyncStatus.FAILED,
                )
            )
            .where(
                or_(
                    config.BILLING_PROJECTION_STATE.next_project_at == None,  # noqa: E711
                    config.BILLING_PROJECTION_STATE.next_project_at <= now,
                )
            )
            .where(
                or_(
                    config.BILLING_PROJECTION_STATE.locked_at == None,  # noqa: E711
                    config.BILLING_PROJECTION_STATE.locked_at < stale_lock,
                )
            )
            .order_by(config.BILLING_PROJECTION_STATE.dirty_since, "ASC")
            .limit(limit)
            .for_update(skip_locked=True)
        )
        rows = await db_connection.exec(query)
        for row in rows:
            row.projection_status = SyncStatus.SYNCING
            row.locked_at = now
            row.updated_at = now
        await db_connection.update(rows)
        return rows


async def fetch_canonical_object(
    *,
    stripe_id: str,
    object_type: str,
    config: BillingConfig,
) -> dict[str, Any]:
    api_key = config.STRIPE_API_KEY

    if object_type == "customer":
        return stripe_object_to_dict(
            stripe.Customer.retrieve(stripe_id, api_key=api_key)
        )
    if object_type == "subscription":
        return stripe_object_to_dict(
            stripe.Subscription.retrieve(
                stripe_id,
                api_key=api_key,
                expand=[
                    "customer",
                    "items.data.price.product",
                    "latest_invoice.payment_intent",
                ],
            )
        )
    if object_type == "checkout.session":
        checkout_session = stripe.checkout.Session.retrieve(
            stripe_id,
            api_key=api_key,
            expand=["customer", "subscription", "payment_intent", "invoice"],
        )
        payload = stripe_object_to_dict(checkout_session)
        line_items = stripe.checkout.Session.list_line_items(
            stripe_id,
            api_key=api_key,
            expand=["data.price.product"],
        )
        payload["line_items"] = {
            "object": "list",
            "data": [stripe_object_to_dict(line_item) for line_item in line_items],
        }
        return payload
    if object_type == "product":
        return stripe_object_to_dict(
            stripe.Product.retrieve(stripe_id, api_key=api_key)
        )
    if object_type == "price":
        return stripe_object_to_dict(
            stripe.Price.retrieve(stripe_id, api_key=api_key, expand=["product"])
        )
    if object_type == "invoice":
        return stripe_object_to_dict(
            stripe.Invoice.retrieve(
                stripe_id,
                api_key=api_key,
                expand=[
                    "customer",
                    "subscription",
                    "payment_intent",
                    "lines.data.price.product",
                ],
            )
        )
    if object_type == "payment_intent":
        return stripe_object_to_dict(
            stripe.PaymentIntent.retrieve(
                stripe_id,
                api_key=api_key,
                expand=["customer", "invoice"],
            )
        )
    if object_type == "charge":
        return stripe_object_to_dict(
            stripe.Charge.retrieve(
                stripe_id,
                api_key=api_key,
                expand=["customer", "payment_intent", "invoice"],
            )
        )

    raise ValueError(f"Unsupported stripe object type: {object_type}")


async def finalize_object_success(
    *,
    stripe_object: models.StripeObject,
    reconciled_payload: dict[str, Any],
    config: BillingConfig,
    db_connection: DBConnection,
) -> None:
    now = utcnow()
    async with db_connection.transaction():
        query = (
            select(config.BILLING_STRIPE_OBJECT)
            .where(config.BILLING_STRIPE_OBJECT.id == stripe_object.id)
            .for_update()
        )
        current_rows = await db_connection.exec(query)
        if not current_rows:
            return

        current = current_rows[0]
        current.object_type = reconciled_payload.get("object", current.object_type)
        current.api_version = stripe_object.api_version
        payload_digest = payload_hash(reconciled_payload)
        current.generic_payload = (
            reconciled_payload if current.object_type not in SUPPORTED_OBJECT_TYPES else None
        )
        current.generic_payload_hash = (
            payload_digest if current.object_type not in SUPPORTED_OBJECT_TYPES else ""
        )
        current.charge = (
            StripeChargeAdapter.validate_python(
                reconciled_payload,
                api_version=current.api_version,
            )
            if current.object_type == "charge"
            else None
        )
        current.charge_hash = payload_digest if current.object_type == "charge" else ""
        current.checkout_session = (
            StripeCheckoutSessionAdapter.validate_python(
                reconciled_payload,
                api_version=current.api_version,
            )
            if current.object_type == "checkout.session"
            else None
        )
        current.checkout_session_hash = (
            payload_digest if current.object_type == "checkout.session" else ""
        )
        current.customer = (
            StripeCustomerAdapter.validate_python(
                reconciled_payload,
                api_version=current.api_version,
            )
            if current.object_type == "customer"
            else None
        )
        current.customer_hash = payload_digest if current.object_type == "customer" else ""
        current.invoice = (
            StripeInvoiceAdapter.validate_python(
                reconciled_payload,
                api_version=current.api_version,
            )
            if current.object_type == "invoice"
            else None
        )
        current.invoice_hash = payload_digest if current.object_type == "invoice" else ""
        current.payment_intent = (
            StripePaymentIntentAdapter.validate_python(
                reconciled_payload,
                api_version=current.api_version,
            )
            if current.object_type == "payment_intent"
            else None
        )
        current.payment_intent_hash = (
            payload_digest if current.object_type == "payment_intent" else ""
        )
        current.price = (
            StripePriceAdapter.validate_python(
                reconciled_payload,
                api_version=current.api_version,
            )
            if current.object_type == "price"
            else None
        )
        current.price_hash = payload_digest if current.object_type == "price" else ""
        current.product = (
            StripeProductAdapter.validate_python(
                reconciled_payload,
                api_version=current.api_version,
            )
            if current.object_type == "product"
            else None
        )
        current.product_hash = payload_digest if current.object_type == "product" else ""
        current.subscription = (
            StripeSubscriptionAdapter.validate_python(
                reconciled_payload,
                api_version=current.api_version,
            )
            if current.object_type == "subscription"
            else None
        )
        current.subscription_hash = (
            payload_digest if current.object_type == "subscription" else ""
        )
        current.stripe_customer_id = extract_customer_id(reconciled_payload)
        current.internal_user_id = extract_internal_user_id(reconciled_payload)
        current.remote_created_at = to_datetime(reconciled_payload.get("created"))
        current.remote_deleted_at = now if reconciled_payload.get("deleted") else None
        current.last_reconciled_at = now
        current.locked_at = None
        current.updated_at = now
        current.last_error = None
        current.retry_count = 0
        current.next_reconcile_at = None

        if (
            stripe_object.latest_event_created_at
            and current.latest_event_created_at
            and current.latest_event_created_at > stripe_object.latest_event_created_at
        ):
            current.sync_status = SyncStatus.PENDING
            current.dirty_since = current.dirty_since or now
            current.next_reconcile_at = now
        else:
            current.sync_status = SyncStatus.CLEAN
            current.dirty_since = None

        await db_connection.update([current])


async def finalize_object_failure(
    *,
    stripe_object: models.StripeObject,
    error: Exception,
    config: BillingConfig,
    db_connection: DBConnection,
) -> None:
    now = utcnow()
    async with db_connection.transaction():
        query = (
            select(config.BILLING_STRIPE_OBJECT)
            .where(config.BILLING_STRIPE_OBJECT.id == stripe_object.id)
            .for_update()
        )
        current_rows = await db_connection.exec(query)
        if not current_rows:
            return

        current = current_rows[0]
        current.sync_status = SyncStatus.FAILED
        current.retry_count = current.retry_count + 1
        current.last_error = str(error)
        current.locked_at = None
        current.updated_at = now
        current.next_reconcile_at = next_retry_time(current.retry_count)
        current.dirty_since = current.dirty_since or now
        await db_connection.update([current])


async def finalize_projection_success(
    *,
    projection_state: models.BillingProjectionState,
    config: BillingConfig,
    db_connection: DBConnection,
) -> None:
    now = utcnow()
    async with db_connection.transaction():
        query = (
            select(config.BILLING_PROJECTION_STATE)
            .where(config.BILLING_PROJECTION_STATE.id == projection_state.id)
            .for_update()
        )
        rows = await db_connection.exec(query)
        if not rows:
            return

        current = rows[0]
        current.projection_status = SyncStatus.CLEAN
        current.dirty_since = None
        current.last_projected_at = now
        current.next_project_at = None
        current.locked_at = None
        current.retry_count = 0
        current.last_error = None
        current.updated_at = now
        await db_connection.update([current])


async def finalize_projection_failure(
    *,
    projection_state: models.BillingProjectionState,
    error: Exception,
    config: BillingConfig,
    db_connection: DBConnection,
) -> None:
    now = utcnow()
    async with db_connection.transaction():
        query = (
            select(config.BILLING_PROJECTION_STATE)
            .where(config.BILLING_PROJECTION_STATE.id == projection_state.id)
            .for_update()
        )
        rows = await db_connection.exec(query)
        if not rows:
            return

        current = rows[0]
        current.projection_status = SyncStatus.FAILED
        current.retry_count = current.retry_count + 1
        current.last_error = str(error)
        current.next_project_at = next_retry_time(current.retry_count)
        current.locked_at = None
        current.updated_at = now
        current.dirty_since = current.dirty_since or now
        await db_connection.update([current])


async def reschedule_projection(
    *,
    projection_state: models.BillingProjectionState,
    delay_seconds: int,
    config: BillingConfig,
    db_connection: DBConnection,
) -> None:
    now = utcnow()
    async with db_connection.transaction():
        query = (
            select(config.BILLING_PROJECTION_STATE)
            .where(config.BILLING_PROJECTION_STATE.id == projection_state.id)
            .for_update()
        )
        rows = await db_connection.exec(query)
        if not rows:
            return

        current = rows[0]
        current.projection_status = SyncStatus.PENDING
        current.next_project_at = now + timedelta(seconds=delay_seconds)
        current.locked_at = None
        current.updated_at = now
        await db_connection.update([current])


async def find_user_for_customer(
    *,
    stripe_customer_id: str,
    internal_user_id: UUID | None,
    config: BillingConfig,
    db_connection: DBConnection,
) -> models.UserBillingMixin | None:
    if internal_user_id:
        query = select(config.BILLING_USER).where(  # type: ignore[arg-type]
            config.BILLING_USER.id == internal_user_id
        )
        users = await db_connection.exec(query)
        if users:
            return users[0]

    query = select(config.BILLING_USER).where(
        config.BILLING_USER.stripe_customer_id == stripe_customer_id
    )
    users = await db_connection.exec(query)
    return users[0] if users else None


async def sync_user_customer_link(
    *,
    user: models.UserBillingMixin,
    stripe_customer_id: str,
    db_connection: DBConnection,
) -> None:
    if user.stripe_customer_id != stripe_customer_id:
        user.stripe_customer_id = stripe_customer_id
        await db_connection.update([user])
