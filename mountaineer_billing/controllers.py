from typing import TYPE_CHECKING, Any, cast

import stripe
from fastapi import APIRouter, Depends, Request

from mountaineer import CoreDependencies

from mountaineer_billing import daemons
from mountaineer_billing.config import BillingConfig
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


async def stripe_webhook(
    request: Request,
    config: BillingConfig = Depends(
        CoreDependencies.get_config_with_type(BillingConfig)
    ),
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

    reconcile_run = cast(Any, daemons.ReconcileStripeObjects().run)
    project_run = cast(Any, daemons.ProjectStripeBilling().run)

    await daemons.UpdateStripe().run(payload=event)
    await reconcile_run(limit=25, _blocking=False)
    await project_run(limit=25, _blocking=False)

    return dict(success=True, event_id=event["id"])


def get_billing_router():
    router = APIRouter(prefix="/external/billing")
    router.post("/webhooks/stripe")(stripe_webhook)
    return router
