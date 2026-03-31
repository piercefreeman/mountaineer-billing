from __future__ import annotations

from datetime import timedelta

from iceaxe import DBConnection
from pydantic import BaseModel
from waymark import Depend, RetryPolicy, Workflow, action, workflow

from mountaineer_billing.config import BillingConfig
from mountaineer_billing.enums import SyncStatus
from mountaineer_billing.logging import LOGGER

from .stripe_sync import (
    SUPPORTED_OBJECT_TYPES,
    claim_reconcile_batch,
    extract_customer_id,
    extract_internal_user_id,
    fetch_canonical_object,
    finalize_object_failure,
    finalize_object_success,
    get_billing_config,
    get_db_connection,
    supported_child_objects,
    upsert_projection_state,
    upsert_stripe_object,
    utcnow,
)


class ReconcileStripeObjectsRequest(BaseModel):
    limit: int = 25


class ReconcileStripeObjectsResponse(BaseModel):
    processed_count: int = 0


@workflow
class ReconcileStripeObjects(Workflow):
    async def run(  # type: ignore[override]
        self,
        *,
        limit: int = 25,
    ) -> ReconcileStripeObjectsResponse:
        return await self.run_action(
            reconcile_dirty_stripe_objects(
                ReconcileStripeObjectsRequest(limit=limit)
            ),
            retry=RetryPolicy(attempts=3, backoff_seconds=5),
            timeout=timedelta(seconds=60),
        )


@action
async def reconcile_dirty_stripe_objects(
    request: ReconcileStripeObjectsRequest,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(get_db_connection),  # type: ignore[assignment]
) -> ReconcileStripeObjectsResponse:
    claimed_rows = await claim_reconcile_batch(
        limit=request.limit,
        db_connection=db_connection,
        config=config,
    )

    processed_count = 0
    for claimed_row in claimed_rows:
        try:
            if claimed_row.object_type in SUPPORTED_OBJECT_TYPES:
                reconciled_payload = await fetch_canonical_object(
                    stripe_id=claimed_row.stripe_id,
                    object_type=claimed_row.object_type,
                    config=config,
                )
            else:
                reconciled_payload = claimed_row.payload

            root_key = (claimed_row.object_type, claimed_row.stripe_id)
            for (object_type, stripe_id), child_payload in supported_child_objects(
                reconciled_payload
            ).items():
                if (object_type, stripe_id) == root_key:
                    continue

                await upsert_stripe_object(
                    stripe_id=stripe_id,
                    object_type=object_type,
                    livemode=claimed_row.livemode,
                    payload=child_payload,
                    sync_status=SyncStatus.CLEAN,
                    last_reconciled_at=utcnow(),
                    db_connection=db_connection,
                    config=config,
                )

            customer_id = extract_customer_id(reconciled_payload)
            internal_user_id = extract_internal_user_id(reconciled_payload)
            if customer_id:
                await upsert_projection_state(
                    stripe_customer_id=customer_id,
                    internal_user_id=internal_user_id,
                    db_connection=db_connection,
                    config=config,
                )

            await finalize_object_success(
                stripe_object=claimed_row,
                reconciled_payload=reconciled_payload,
                config=config,
                db_connection=db_connection,
            )
            processed_count += 1
        except Exception as exc:
            LOGGER.exception(
                "Failed to reconcile stripe object %s (%s)",
                claimed_row.stripe_id,
                claimed_row.object_type,
            )
            await finalize_object_failure(
                stripe_object=claimed_row,
                error=exc,
                config=config,
                db_connection=db_connection,
            )

    return ReconcileStripeObjectsResponse(processed_count=processed_count)
