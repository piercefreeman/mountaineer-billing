from typing import TYPE_CHECKING, Any

import stripe
from fastapi import APIRouter, Depends, Request
from iceaxe import DBConnection
from iceaxe.mountaineer import DatabaseDependencies

from mountaineer import CoreDependencies

from mountaineer_billing.config import BillingConfig
from mountaineer_billing.daemons import ReloadStripeObject
from mountaineer_billing.daemons.reload_stripe_object import (
    extract_customer_id,
    nested_id,
    stripe_object_to_dict,
    to_datetime,
)
from mountaineer_billing.logging import LOGGER

if TYPE_CHECKING:
    # More recent versions of stripe have refactored errors to be importable
    # from the main `stripe` package and throw a warning if we try to import from
    # the deprecated `stripe.error` package. However our typeshed definitions don't
    # expose errors from the main package, so we need to import from the deprecated
    # package.
    from stripe.error import SignatureVerificationError
else:
    from stripe import SignatureVerificationError

router = APIRouter(prefix="/external/billing")


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    config: BillingConfig = Depends(
        CoreDependencies.get_config_with_type(BillingConfig)
    ),
    db_connection: DBConnection = Depends(DatabaseDependencies.get_db_connection),
):
    payload = await request.body()
    signature_header = request.headers["stripe-signature"]

    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature_header,
            config.STRIPE_WEBHOOK_SECRET,
            api_key=config.STRIPE_API_KEY,
        )
    except ValueError as e:
        # Invalid payload
        raise e
    except SignatureVerificationError as e:
        # Invalid signature
        LOGGER.error(f"Invalid stripe webhook signature: {e}: {signature_header}")
        raise e

    event_payload = stripe_object_to_dict(event)
    stripe_event_id = event_payload.get("id")
    stripe_event_type = event_payload.get("type")
    if not isinstance(stripe_event_id, str) or not isinstance(stripe_event_type, str):
        raise ValueError("Stripe event payload is missing required id or type fields")

    raw_object_payload: dict[str, Any] | None = None
    data = event_payload.get("data")
    if isinstance(data, dict):
        data_object = data.get("object")
        if isinstance(data_object, dict):
            raw_object_payload = data_object

    stripe_object_id = nested_id(raw_object_payload)
    stripe_object_type = (
        raw_object_payload.get("object")
        if raw_object_payload and isinstance(raw_object_payload.get("object"), str)
        else None
    )
    stripe_customer_id = (
        extract_customer_id(raw_object_payload) if raw_object_payload else None
    )

    stripe_event = config.BILLING_STRIPE_EVENT(
        stripe_event_id=stripe_event_id,
        stripe_event_type=stripe_event_type,
        stripe_object_id=stripe_object_id,
        stripe_object_type=stripe_object_type,
        stripe_customer_id=stripe_customer_id,
        livemode=bool(event_payload.get("livemode", False)),
        stripe_created_at=to_datetime(event_payload.get("created")),
        payload=event_payload,
    )
    upsert_results = await db_connection.upsert(
        [stripe_event],
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
        returning_fields=(config.BILLING_STRIPE_EVENT.id,),
    )
    if not upsert_results:
        raise ValueError("Failed to persist validated Stripe event")

    saved_event_id = upsert_results[0][0]
    await ReloadStripeObject().run(event_id=saved_event_id)

    return dict(success=True, event_id=stripe_event_id)
