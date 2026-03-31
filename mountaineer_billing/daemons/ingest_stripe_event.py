from __future__ import annotations

from datetime import timedelta
from typing import Any

from iceaxe import DBConnection
from pydantic import BaseModel
from waymark import Depend, RetryPolicy, Workflow, action, workflow

from mountaineer_billing.config import BillingConfig
from mountaineer_billing.enums import SyncStatus

from .stripe_sync import (
    extract_customer_id,
    extract_primary_object,
    get_billing_config,
    get_db_connection,
    to_datetime,
    upsert_stripe_object,
    utcnow,
)


class StoreStripeEventRequest(BaseModel):
    payload: dict[str, Any]


class StoreStripeEventResponse(BaseModel):
    stripe_event_id: str
    stripe_object_id: str | None = None
    stripe_object_type: str | None = None
    stripe_customer_id: str | None = None


@workflow
class UpdateStripe(Workflow):
    async def run(  # type: ignore[override]
        self,
        *,
        payload: dict[str, Any],
    ) -> StoreStripeEventResponse:
        return await self.run_action(
            store_stripe_event(StoreStripeEventRequest(payload=payload)),
            retry=RetryPolicy(attempts=3, backoff_seconds=5),
            timeout=timedelta(seconds=30),
        )


@action
async def store_stripe_event(
    request: StoreStripeEventRequest,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(get_db_connection),  # type: ignore[assignment]
) -> StoreStripeEventResponse:
    event_payload = request.payload
    stripe_event_id = event_payload["id"]
    stripe_object_id, stripe_object_type, object_snapshot = extract_primary_object(
        event_payload
    )
    stripe_created_at = to_datetime(event_payload.get("created"))
    stripe_customer_id = (
        extract_customer_id(object_snapshot) if object_snapshot else None
    )

    event_obj = config.BILLING_STRIPE_EVENT(
        stripe_event_id=stripe_event_id,
        stripe_event_type=event_payload["type"],
        stripe_object_id=stripe_object_id,
        stripe_object_type=stripe_object_type,
        stripe_customer_id=stripe_customer_id,
        livemode=bool(event_payload.get("livemode", False)),
        stripe_created_at=stripe_created_at,
        payload=event_payload,
    )
    await db_connection.upsert(
        [event_obj],
        conflict_fields=(config.BILLING_STRIPE_EVENT.stripe_event_id,),
        update_fields=(
            config.BILLING_STRIPE_EVENT.stripe_event_type,
            config.BILLING_STRIPE_EVENT.stripe_object_id,
            config.BILLING_STRIPE_EVENT.stripe_object_type,
            config.BILLING_STRIPE_EVENT.stripe_customer_id,
            config.BILLING_STRIPE_EVENT.livemode,
            config.BILLING_STRIPE_EVENT.stripe_created_at,
            config.BILLING_STRIPE_EVENT.payload,
        ),
    )

    if stripe_object_id and stripe_object_type and object_snapshot:
        now = utcnow()
        await upsert_stripe_object(
            stripe_id=stripe_object_id,
            object_type=stripe_object_type,
            livemode=bool(event_payload.get("livemode", False)),
            payload=object_snapshot,
            api_version=event_payload.get("api_version"),
            sync_status=SyncStatus.PENDING,
            latest_event_created_at=stripe_created_at,
            dirty_since=now,
            next_reconcile_at=now,
            db_connection=db_connection,
            config=config,
        )

    return StoreStripeEventResponse(
        stripe_event_id=stripe_event_id,
        stripe_object_id=stripe_object_id,
        stripe_object_type=stripe_object_type,
        stripe_customer_id=stripe_customer_id,
    )
