from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any, Callable, cast

import stripe
from iceaxe import DBConnection, func, select
from pydantic import BaseModel, Field

from mountaineer_billing.cli.sync_up import (
    HasPriceMappingData,
    upsert_price_mapping_from_stripe_price,
)
from mountaineer_billing.cli.waymark import run_workflow_nonblocking
from mountaineer_billing.config import BillingConfig
from mountaineer_billing.daemons.materialize_subscriptions import (
    MaterializeSubscriptions,
)
from mountaineer_billing.daemons.reload_stripe_object import (
    OBJECT_TYPE_TO_ADAPTER,
    stripe_object_to_dict,
    upsert_stripe_object_snapshot,
)
from mountaineer_billing.logging import LOGGER


def list_charges(**kwargs: Any) -> Any:
    return stripe.Charge.list(**kwargs)


def list_checkout_sessions(**kwargs: Any) -> Any:
    return cast(Any, stripe.checkout.Session).list(**kwargs)


def list_customers(**kwargs: Any) -> Any:
    return stripe.Customer.list(**kwargs)


def list_invoices(**kwargs: Any) -> Any:
    return stripe.Invoice.list(**kwargs)


def list_payment_intents(**kwargs: Any) -> Any:
    return stripe.PaymentIntent.list(**kwargs)


def list_prices(**kwargs: Any) -> Any:
    return stripe.Price.list(**kwargs)


def list_products(**kwargs: Any) -> Any:
    return stripe.Product.list(**kwargs)


def list_subscriptions(**kwargs: Any) -> Any:
    return stripe.Subscription.list(**kwargs)


@dataclass(frozen=True)
class StripeObjectEndpoint:
    object_type: str
    list_callable: Callable[..., Any]
    request_params: tuple[dict[str, Any], ...] = ({},)


@dataclass
class EndpointSyncProgress:
    object_type: str
    started_at: float
    local_estimate: int | None = None
    last_logged_at: float = 0.0
    last_logged_synced_count: int = 0


def format_duration(seconds: float) -> str:
    rounded_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(rounded_seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}h{minutes:02d}m{remaining_seconds:02d}s"
    if minutes:
        return f"{minutes}m{remaining_seconds:02d}s"
    return f"{remaining_seconds}s"


SYNC_DOWN_ENDPOINTS = (
    StripeObjectEndpoint("charge", list_charges),
    StripeObjectEndpoint("checkout.session", list_checkout_sessions),
    StripeObjectEndpoint("customer", list_customers),
    StripeObjectEndpoint("invoice", list_invoices),
    StripeObjectEndpoint("payment_intent", list_payment_intents),
    StripeObjectEndpoint(
        "price",
        list_prices,
        request_params=({}, {"active": False}),
    ),
    StripeObjectEndpoint("product", list_products),
    StripeObjectEndpoint(
        "subscription",
        list_subscriptions,
        request_params=({"status": "all"},),
    ),
)


class SyncDownSummary(BaseModel):
    synced_counts: dict[str, int] = Field(default_factory=dict)
    price_mappings_upserted: int = 0
    customers_enqueued: int = 0

    @property
    def customers_materialized(self) -> int:
        return self.customers_enqueued


class StripeSyncDown:
    def __init__(self, config: BillingConfig):
        self.config = config
        self.pagination_limit = 50
        self.api_version = stripe.api_version
        self.progress_log_interval_objects = 500
        self.progress_log_interval_seconds = 30.0

    async def sync_objects(self, db_connection: DBConnection) -> SyncDownSummary:
        sync_started_at = monotonic()
        LOGGER.info(
            "Starting Stripe sync down using API version %s",
            self.api_version,
        )

        customer_ids_to_materialize: set[str] = set()
        summary = SyncDownSummary()

        total_endpoints = len(SYNC_DOWN_ENDPOINTS)
        for endpoint_index, endpoint in enumerate(SYNC_DOWN_ENDPOINTS, start=1):
            synced_count = 0
            seen_stripe_ids: set[str] = set()
            local_estimate = await self._local_object_count_estimate(
                db_connection=db_connection,
                object_type=endpoint.object_type,
            )
            progress = EndpointSyncProgress(
                object_type=endpoint.object_type,
                started_at=monotonic(),
                local_estimate=local_estimate,
                last_logged_at=monotonic(),
            )
            LOGGER.info(
                "Syncing Stripe %s objects (%s/%s%s)",
                endpoint.object_type,
                endpoint_index,
                total_endpoints,
                (
                    f", local estimate {local_estimate}"
                    if local_estimate is not None
                    else ", local estimate unavailable"
                ),
            )

            for raw_object in self._iter_remote_objects(endpoint):
                payload_data = stripe_object_to_dict(raw_object)
                stripe_id = payload_data.get("id")
                if not isinstance(stripe_id, str):
                    LOGGER.warning(
                        "Skipping Stripe %s without id during sync down",
                        endpoint.object_type,
                    )
                    continue

                if stripe_id in seen_stripe_ids:
                    continue
                seen_stripe_ids.add(stripe_id)

                typed_payload = OBJECT_TYPE_TO_ADAPTER[
                    endpoint.object_type
                ].validate_python(
                    payload_data,
                    api_version=self.api_version,
                )
                persisted_object = await upsert_stripe_object_snapshot(
                    object_type=endpoint.object_type,
                    object_payload=cast(BaseModel, typed_payload),
                    livemode=bool(payload_data.get("livemode", False)),
                    latest_event_created_at=None,
                    config=self.config,
                    db_connection=db_connection,
                    include_latest_event_created_at=False,
                )
                synced_count += 1

                if endpoint.object_type == "price":
                    price_payload = cast(HasPriceMappingData, typed_payload)
                    stored_mapping = await upsert_price_mapping_from_stripe_price(
                        config=self.config,
                        remote_price=price_payload,
                        db_connection=db_connection,
                    )
                    if stored_mapping:
                        summary.price_mappings_upserted += 1

                if persisted_object.stripe_customer_id:
                    customer_ids_to_materialize.add(persisted_object.stripe_customer_id)

                self._maybe_log_endpoint_progress(
                    progress=progress,
                    synced_count=synced_count,
                )

            summary.synced_counts[endpoint.object_type] = synced_count
            self._log_endpoint_completed(progress=progress, synced_count=synced_count)

        if customer_ids_to_materialize:
            LOGGER.info(
                "Queueing subscription materialization for %s customers",
                len(customer_ids_to_materialize),
            )
        for stripe_customer_id in sorted(customer_ids_to_materialize):
            try:
                await run_workflow_nonblocking(
                    MaterializeSubscriptions().run,
                    stripe_customer_id=stripe_customer_id,
                )
            except Exception as exc:
                LOGGER.warning(
                    "Skipping subscription materialization for customer %s: %s",
                    stripe_customer_id,
                    exc,
                )
                continue

            summary.customers_enqueued += 1

        LOGGER.info(
            "Completed Stripe sync down in %s: %s Stripe objects synced, %s price mappings upserted, %s customers enqueued",
            format_duration(monotonic() - sync_started_at),
            sum(summary.synced_counts.values()),
            summary.price_mappings_upserted,
            summary.customers_enqueued,
        )
        return summary

    def _iter_remote_objects(self, endpoint: StripeObjectEndpoint):
        for request_params in endpoint.request_params:
            list_response = endpoint.list_callable(
                limit=self.pagination_limit,
                api_key=self.config.STRIPE_API_KEY,
                stripe_version=self.api_version,
                **request_params,
            )
            yield from list_response.auto_paging_iter()

    async def _local_object_count_estimate(
        self,
        *,
        db_connection: DBConnection,
        object_type: str,
    ) -> int | None:
        stripe_object_model = self.config.BILLING_MODELS.STRIPE_OBJECT
        result = await db_connection.exec(
            select(func.count(stripe_object_model.stripe_id)).where(
                stripe_object_model.object_type == object_type
            )
        )
        if not result:
            return None

        count = int(result[0])
        return count if count > 0 else None

    def _maybe_log_endpoint_progress(
        self,
        *,
        progress: EndpointSyncProgress,
        synced_count: int,
    ) -> None:
        if synced_count <= 0:
            return

        now = monotonic()
        if (
            synced_count - progress.last_logged_synced_count
            < self.progress_log_interval_objects
            and now - progress.last_logged_at < self.progress_log_interval_seconds
        ):
            return

        elapsed = max(now - progress.started_at, 1e-9)
        objects_per_second = synced_count / elapsed
        local_estimate = progress.local_estimate

        if local_estimate is not None and local_estimate >= synced_count:
            remaining_objects = local_estimate - synced_count
            percent_complete = (synced_count / local_estimate) * 100
            eta_seconds = remaining_objects / objects_per_second
            LOGGER.info(
                "Stripe %s sync progress: %s/%s objects (%.1f%%) in %s at %.1f objects/sec; ETA %s",
                progress.object_type,
                synced_count,
                local_estimate,
                percent_complete,
                format_duration(elapsed),
                objects_per_second,
                format_duration(eta_seconds),
            )
        elif local_estimate is not None:
            LOGGER.info(
                "Stripe %s sync progress: %s objects synced in %s at %.1f objects/sec (exceeded local estimate of %s)",
                progress.object_type,
                synced_count,
                format_duration(elapsed),
                objects_per_second,
                local_estimate,
            )
        else:
            LOGGER.info(
                "Stripe %s sync progress: %s objects synced in %s at %.1f objects/sec",
                progress.object_type,
                synced_count,
                format_duration(elapsed),
                objects_per_second,
            )

        progress.last_logged_at = now
        progress.last_logged_synced_count = synced_count

    def _log_endpoint_completed(
        self,
        *,
        progress: EndpointSyncProgress,
        synced_count: int,
    ) -> None:
        elapsed = max(monotonic() - progress.started_at, 1e-9)
        objects_per_second = synced_count / elapsed if synced_count else 0.0
        local_estimate = progress.local_estimate

        if local_estimate is not None:
            LOGGER.info(
                "Synced %s Stripe %s objects in %s at %.1f objects/sec (local estimate %s)",
                synced_count,
                progress.object_type,
                format_duration(elapsed),
                objects_per_second,
                local_estimate,
            )
        else:
            LOGGER.info(
                "Synced %s Stripe %s objects in %s at %.1f objects/sec",
                synced_count,
                progress.object_type,
                format_duration(elapsed),
                objects_per_second,
            )


__all__ = [
    "SYNC_DOWN_ENDPOINTS",
    "StripeSyncDown",
    "SyncDownSummary",
]
