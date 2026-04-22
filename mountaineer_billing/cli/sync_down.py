from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any, Callable, cast

import stripe
from iceaxe import DBConnection
from pydantic import BaseModel, Field

from mountaineer_billing.cli.sync_down_reporter import (
    LoggingSyncDownReporter,
    SyncDownReporter,
)
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

    async def sync_objects(
        self,
        db_connection: DBConnection,
        *,
        reporter: SyncDownReporter | None = None,
    ) -> SyncDownSummary:
        reporter = reporter or LoggingSyncDownReporter()
        sync_started_at = monotonic()
        reporter.start_sync(api_version=self.api_version)

        customer_ids_to_materialize: set[str] = set()
        summary = SyncDownSummary()

        for endpoint in SYNC_DOWN_ENDPOINTS:
            synced_count = 0
            seen_stripe_ids: set[str] = set()
            progress = EndpointSyncProgress(
                object_type=endpoint.object_type,
                started_at=monotonic(),
                last_logged_at=monotonic(),
            )
            reporter.start_endpoint(object_type=endpoint.object_type)

            for raw_object in self._iter_remote_objects(endpoint):
                payload_data = stripe_object_to_dict(raw_object)
                stripe_id = payload_data.get("id")
                if not isinstance(stripe_id, str):
                    reporter.warning(
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
                    reporter=reporter,
                )

            summary.synced_counts[endpoint.object_type] = synced_count
            self._log_endpoint_completed(
                progress=progress,
                synced_count=synced_count,
                reporter=reporter,
            )

        if customer_ids_to_materialize:
            reporter.queue_materialization(
                customer_count=len(customer_ids_to_materialize),
            )
        for stripe_customer_id in sorted(customer_ids_to_materialize):
            try:
                await run_workflow_nonblocking(
                    MaterializeSubscriptions().run,
                    stripe_customer_id=stripe_customer_id,
                )
            except Exception as exc:
                reporter.warning(
                    "Skipping subscription materialization for customer %s: %s",
                    stripe_customer_id,
                    exc,
                )
                continue

            summary.customers_enqueued += 1

        reporter.complete_sync(
            elapsed_seconds=monotonic() - sync_started_at,
            total_synced=sum(summary.synced_counts.values()),
            price_mappings_upserted=summary.price_mappings_upserted,
            customers_enqueued=summary.customers_enqueued,
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

    def _maybe_log_endpoint_progress(
        self,
        *,
        progress: EndpointSyncProgress,
        synced_count: int,
        reporter: SyncDownReporter,
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
        reporter.update_endpoint(
            object_type=progress.object_type,
            synced_count=synced_count,
            elapsed_seconds=elapsed,
            objects_per_second=objects_per_second,
        )

        progress.last_logged_at = now
        progress.last_logged_synced_count = synced_count

    def _log_endpoint_completed(
        self,
        *,
        progress: EndpointSyncProgress,
        synced_count: int,
        reporter: SyncDownReporter,
    ) -> None:
        elapsed = max(monotonic() - progress.started_at, 1e-9)
        objects_per_second = synced_count / elapsed if synced_count else 0.0
        reporter.complete_endpoint(
            object_type=progress.object_type,
            synced_count=synced_count,
            elapsed_seconds=elapsed,
            objects_per_second=objects_per_second,
        )


__all__ = [
    "SYNC_DOWN_ENDPOINTS",
    "StripeSyncDown",
    "SyncDownSummary",
]
