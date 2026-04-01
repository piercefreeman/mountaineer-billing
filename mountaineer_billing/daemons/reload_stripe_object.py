from __future__ import annotations

import warnings
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import stripe
from iceaxe import DBConnection, select
from iceaxe.mountaineer import DatabaseDependencies
from pydantic import BaseModel
from waymark import Depend, RetryPolicy, Workflow, action, workflow

from mountaineer.dependencies import CoreDependencies

from mountaineer_billing.config import BillingConfig
from mountaineer_billing.dependencies.stripe import INTERNAL_USER_ID_KEY
from mountaineer_billing.enums import SyncStatus
from mountaineer_billing.stripe.types import (
    VERSION_DISCRIMINATOR_FIELD,
    StripeChargeAdapter,
    StripeChargePayload,
    StripeCheckoutSessionAdapter,
    StripeCheckoutSessionPayload,
    StripeCustomerAdapter,
    StripeCustomerPayload,
    StripeEventPayload,
    StripeInvoiceAdapter,
    StripeInvoicePayload,
    StripeObjectPayload,
    StripePaymentIntentAdapter,
    StripePaymentIntentPayload,
    StripePriceAdapter,
    StripePricePayload,
    StripeProductAdapter,
    StripeProductPayload,
    StripeSubscriptionAdapter,
    StripeSubscriptionPayload,
)

OBJECT_TYPE_TO_FIELD = {
    "charge": "charge",
    "checkout.session": "checkout_session",
    "customer": "customer",
    "invoice": "invoice",
    "payment_intent": "payment_intent",
    "price": "price",
    "product": "product",
    "subscription": "subscription",
}

OBJECT_TYPE_TO_ADAPTER = {
    "charge": StripeChargeAdapter,
    "checkout.session": StripeCheckoutSessionAdapter,
    "customer": StripeCustomerAdapter,
    "invoice": StripeInvoiceAdapter,
    "payment_intent": StripePaymentIntentAdapter,
    "price": StripePriceAdapter,
    "product": StripeProductAdapter,
    "subscription": StripeSubscriptionAdapter,
}

STRIPE_OBJECT_UPDATE_FIELD_NAMES = (
    "object_type",
    "api_version",
    "generic_payload",
    "charge",
    "checkout_session",
    "customer",
    "invoice",
    "payment_intent",
    "price",
    "product",
    "subscription",
    "stripe_customer_id",
    "internal_user_id",
    "sync_status",
    "dirty_since",
    "latest_event_created_at",
    "last_reconciled_at",
    "next_reconcile_at",
    "locked_at",
    "retry_count",
    "last_error",
    "remote_created_at",
    "remote_deleted_at",
    "updated_at",
)


def get_billing_config() -> BillingConfig:
    return CoreDependencies.get_config_with_type(BillingConfig)()


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

    customer_id = nested_id(payload.get("customer"))
    if customer_id:
        return customer_id

    return None


def extract_internal_user_id(payload: dict[str, Any]) -> UUID | None:
    metadata_value = get_metadata(payload).get(INTERNAL_USER_ID_KEY)
    if metadata_value:
        try:
            return UUID(metadata_value)
        except ValueError:
            return None

    if payload.get("object") == "checkout.session":
        client_reference_id = payload.get("client_reference_id")
        if isinstance(client_reference_id, str):
            try:
                return UUID(client_reference_id)
            except ValueError:
                return None

    customer = payload.get("customer")
    if isinstance(customer, dict):
        return extract_internal_user_id(customer)

    return None


class ReloadStripeObjectPayload(BaseModel):
    event: StripeEventPayload
    charge: StripeChargePayload = None
    checkout_session: StripeCheckoutSessionPayload = None
    customer: StripeCustomerPayload = None
    invoice: StripeInvoicePayload = None
    payment_intent: StripePaymentIntentPayload = None
    price: StripePricePayload = None
    product: StripeProductPayload = None
    subscription: StripeSubscriptionPayload = None


class ReloadStripeObjectRequest(BaseModel):
    event_id: UUID


class LoadSavedStripeEventResponse(BaseModel):
    event_id: UUID
    stripe_event_id: str
    livemode: bool
    latest_event_created_at: datetime | None = None
    payload: ReloadStripeObjectPayload


class ReloadStripeObjectResponse(BaseModel):
    event_id: UUID
    stripe_event_id: str
    stripe_object_id: str
    object_type: str
    stripe_customer_id: str | None = None


@workflow
class ReloadStripeObject(Workflow):
    async def run(  # type: ignore[override]
        self,
        *,
        event_id: UUID,
    ) -> ReloadStripeObjectResponse:
        hydrated_event = await self.run_action(
            load_saved_stripe_event(ReloadStripeObjectRequest(event_id=event_id)),
            retry=RetryPolicy(attempts=3, backoff_seconds=5),
            timeout=timedelta(seconds=30),
        )

        if hydrated_event.payload.charge is not None:
            return await self.run_action(
                reload_charge(hydrated_event),
                retry=RetryPolicy(attempts=3, backoff_seconds=5),
                timeout=timedelta(seconds=30),
            )
        if hydrated_event.payload.checkout_session is not None:
            return await self.run_action(
                reload_checkout_session(hydrated_event),
                retry=RetryPolicy(attempts=3, backoff_seconds=5),
                timeout=timedelta(seconds=30),
            )
        if hydrated_event.payload.customer is not None:
            return await self.run_action(
                reload_customer(hydrated_event),
                retry=RetryPolicy(attempts=3, backoff_seconds=5),
                timeout=timedelta(seconds=30),
            )
        if hydrated_event.payload.invoice is not None:
            return await self.run_action(
                reload_invoice(hydrated_event),
                retry=RetryPolicy(attempts=3, backoff_seconds=5),
                timeout=timedelta(seconds=30),
            )
        if hydrated_event.payload.payment_intent is not None:
            return await self.run_action(
                reload_payment_intent(hydrated_event),
                retry=RetryPolicy(attempts=3, backoff_seconds=5),
                timeout=timedelta(seconds=30),
            )
        if hydrated_event.payload.price is not None:
            return await self.run_action(
                reload_price(hydrated_event),
                retry=RetryPolicy(attempts=3, backoff_seconds=5),
                timeout=timedelta(seconds=30),
            )
        if hydrated_event.payload.product is not None:
            return await self.run_action(
                reload_product(hydrated_event),
                retry=RetryPolicy(attempts=3, backoff_seconds=5),
                timeout=timedelta(seconds=30),
            )
        if hydrated_event.payload.subscription is not None:
            return await self.run_action(
                reload_subscription(hydrated_event),
                retry=RetryPolicy(attempts=3, backoff_seconds=5),
                timeout=timedelta(seconds=30),
            )

        raise ValueError(
            f"Stripe event {hydrated_event.stripe_event_id} does not contain a "
            "supported object payload"
        )


@action
async def load_saved_stripe_event(
    request: ReloadStripeObjectRequest,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(DatabaseDependencies.get_db_connection),  # type: ignore[assignment]
) -> LoadSavedStripeEventResponse:
    event_query = select(config.BILLING_STRIPE_EVENT).where(
        config.BILLING_STRIPE_EVENT.id == request.event_id
    )
    saved_events = await db_connection.exec(event_query)
    if not saved_events:
        raise ValueError(f"Stripe event {request.event_id} was not found")

    saved_event = saved_events[0]
    stripe_event = stripe.Event.construct_from(saved_event.payload, config.STRIPE_API_KEY)
    stripe_object = stripe_event.data.object
    stripe_object_payload = stripe_object_to_dict(stripe_object)
    object_type = stripe_object_payload.get("object")
    api_version = saved_event.payload.get("api_version")

    payload_kwargs: dict[str, Any] = {
        "event": saved_event.typed_payload,
    }

    if object_type in OBJECT_TYPE_TO_ADAPTER:
        adapter = OBJECT_TYPE_TO_ADAPTER[object_type]
        field_name = OBJECT_TYPE_TO_FIELD[object_type]
        payload_kwargs[field_name] = adapter.validate_python(
            stripe_object_payload,
            api_version=api_version,
        )

    return LoadSavedStripeEventResponse(
        event_id=saved_event.id,
        stripe_event_id=saved_event.stripe_event_id,
        livemode=saved_event.livemode,
        latest_event_created_at=saved_event.stripe_created_at,
        payload=ReloadStripeObjectPayload(**payload_kwargs),
    )


@action
async def reload_charge(
    request: LoadSavedStripeEventResponse,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(DatabaseDependencies.get_db_connection),  # type: ignore[assignment]
) -> ReloadStripeObjectResponse:
    if request.payload.charge is None:
        raise ValueError("Charge payload is required")
    return await _reload_stripe_object(
        request=request,
        object_type="charge",
        object_payload=request.payload.charge,
        config=config,
        db_connection=db_connection,
    )


@action
async def reload_checkout_session(
    request: LoadSavedStripeEventResponse,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(DatabaseDependencies.get_db_connection),  # type: ignore[assignment]
) -> ReloadStripeObjectResponse:
    if request.payload.checkout_session is None:
        raise ValueError("Checkout session payload is required")
    return await _reload_stripe_object(
        request=request,
        object_type="checkout.session",
        object_payload=request.payload.checkout_session,
        config=config,
        db_connection=db_connection,
    )


@action
async def reload_customer(
    request: LoadSavedStripeEventResponse,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(DatabaseDependencies.get_db_connection),  # type: ignore[assignment]
) -> ReloadStripeObjectResponse:
    if request.payload.customer is None:
        raise ValueError("Customer payload is required")
    return await _reload_stripe_object(
        request=request,
        object_type="customer",
        object_payload=request.payload.customer,
        config=config,
        db_connection=db_connection,
    )


@action
async def reload_invoice(
    request: LoadSavedStripeEventResponse,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(DatabaseDependencies.get_db_connection),  # type: ignore[assignment]
) -> ReloadStripeObjectResponse:
    if request.payload.invoice is None:
        raise ValueError("Invoice payload is required")
    return await _reload_stripe_object(
        request=request,
        object_type="invoice",
        object_payload=request.payload.invoice,
        config=config,
        db_connection=db_connection,
    )


@action
async def reload_payment_intent(
    request: LoadSavedStripeEventResponse,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(DatabaseDependencies.get_db_connection),  # type: ignore[assignment]
) -> ReloadStripeObjectResponse:
    if request.payload.payment_intent is None:
        raise ValueError("Payment intent payload is required")
    return await _reload_stripe_object(
        request=request,
        object_type="payment_intent",
        object_payload=request.payload.payment_intent,
        config=config,
        db_connection=db_connection,
    )


@action
async def reload_price(
    request: LoadSavedStripeEventResponse,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(DatabaseDependencies.get_db_connection),  # type: ignore[assignment]
) -> ReloadStripeObjectResponse:
    if request.payload.price is None:
        raise ValueError("Price payload is required")
    return await _reload_stripe_object(
        request=request,
        object_type="price",
        object_payload=request.payload.price,
        config=config,
        db_connection=db_connection,
    )


@action
async def reload_product(
    request: LoadSavedStripeEventResponse,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(DatabaseDependencies.get_db_connection),  # type: ignore[assignment]
) -> ReloadStripeObjectResponse:
    if request.payload.product is None:
        raise ValueError("Product payload is required")
    return await _reload_stripe_object(
        request=request,
        object_type="product",
        object_payload=request.payload.product,
        config=config,
        db_connection=db_connection,
    )


@action
async def reload_subscription(
    request: LoadSavedStripeEventResponse,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(DatabaseDependencies.get_db_connection),  # type: ignore[assignment]
) -> ReloadStripeObjectResponse:
    if request.payload.subscription is None:
        raise ValueError("Subscription payload is required")
    return await _reload_stripe_object(
        request=request,
        object_type="subscription",
        object_payload=request.payload.subscription,
        config=config,
        db_connection=db_connection,
    )


async def _reload_stripe_object(
    *,
    request: LoadSavedStripeEventResponse,
    object_type: str,
    object_payload: StripeObjectPayload,
    config: BillingConfig,
    db_connection: DBConnection,
) -> ReloadStripeObjectResponse:
    now = utcnow()
    payload_data = object_payload.model_dump(mode="json")
    stripe_id = payload_data.get("id")
    if not isinstance(stripe_id, str):
        raise ValueError(f"Stripe {object_type} payload is missing an id")

    api_version = payload_data.get(VERSION_DISCRIMINATOR_FIELD)
    if api_version is not None and not isinstance(api_version, str):
        raise ValueError(
            f"Stripe {object_type} payload contains an invalid api version"
        )

    field_name = OBJECT_TYPE_TO_FIELD[object_type]
    payload_fields = {field: None for field in OBJECT_TYPE_TO_FIELD.values()}
    payload_fields[field_name] = object_payload

    stripe_customer_id = extract_customer_id(payload_data)
    stripe_object = config.BILLING_STRIPE_OBJECT(
        stripe_id=stripe_id,
        object_type=object_type,
        livemode=bool(payload_data.get("livemode", request.livemode)),
        api_version=api_version,
        generic_payload=None,
        stripe_customer_id=stripe_customer_id,
        internal_user_id=extract_internal_user_id(payload_data),
        sync_status=SyncStatus.CLEAN,
        dirty_since=None,
        latest_event_created_at=request.latest_event_created_at,
        last_reconciled_at=now,
        next_reconcile_at=None,
        locked_at=None,
        retry_count=0,
        last_error=None,
        remote_created_at=to_datetime(payload_data.get("created")),
        remote_deleted_at=now if payload_data.get("deleted") else None,
        updated_at=now,
        **payload_fields,
    )
    await db_connection.upsert(
        [stripe_object],
        conflict_fields=(
            config.BILLING_STRIPE_OBJECT.stripe_id,
            config.BILLING_STRIPE_OBJECT.livemode,
        ),
        update_fields=tuple(
            getattr(config.BILLING_STRIPE_OBJECT, field_name)
            for field_name in STRIPE_OBJECT_UPDATE_FIELD_NAMES
        ),
    )

    return ReloadStripeObjectResponse(
        event_id=request.event_id,
        stripe_event_id=request.stripe_event_id,
        stripe_object_id=stripe_id,
        object_type=object_type,
        stripe_customer_id=stripe_customer_id,
    )


__all__ = [
    "ReloadStripeObject",
    "ReloadStripeObjectPayload",
    "ReloadStripeObjectRequest",
    "ReloadStripeObjectResponse",
]
