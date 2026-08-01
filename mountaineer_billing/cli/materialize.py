from __future__ import annotations

from iceaxe import DBConnection, select
from pydantic import BaseModel

from mountaineer_billing.cli.waymark import run_workflow_nonblocking
from mountaineer_billing.config import BillingConfig
from mountaineer_billing.daemons.materialize_subscriptions import (
    MaterializeSubscriptions,
)
from mountaineer_billing.logging import LOGGER


class MaterializeSyncSummary(BaseModel):
    users_selected: int = 0
    users_enqueued: int = 0
    users_failed: int = 0


class StripeSyncMaterialize:
    def __init__(self, config: BillingConfig):
        self.config = config

    async def materialize_users(
        self,
        db_connection: DBConnection,
    ) -> MaterializeSyncSummary:
        users = await db_connection.exec(
            select(self.config.BILLING_MODELS.USER).where(
                self.config.BILLING_MODELS.USER.stripe_customer_id != None  # noqa: E711
            )
        )
        summary = MaterializeSyncSummary(users_selected=len(users))

        LOGGER.info(
            "Starting Stripe materialize sync for %s local users",
            summary.users_selected,
        )

        for user in sorted(users, key=lambda user: str(user.id)):
            stripe_customer_id = user.stripe_customer_id
            if stripe_customer_id is None:
                continue

            try:
                await run_workflow_nonblocking(
                    MaterializeSubscriptions().run,
                    stripe_customer_id=stripe_customer_id,
                    internal_user_id=user.id,
                )
            except Exception as exc:
                summary.users_failed += 1
                LOGGER.warning(
                    "Skipping subscription materialization for user %s / customer %s: %s",
                    user.id,
                    stripe_customer_id,
                    exc,
                )
                continue

            summary.users_enqueued += 1

        LOGGER.info(
            "Queued Stripe materialize sync: %s users enqueued, %s failed",
            summary.users_enqueued,
            summary.users_failed,
        )
        return summary


__all__ = [
    "MaterializeSyncSummary",
    "StripeSyncMaterialize",
]
