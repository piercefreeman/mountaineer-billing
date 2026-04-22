from __future__ import annotations

from io import StringIO
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import stripe
from click.testing import CliRunner
from iceaxe import DBConnection, select
from rich.console import Console

from mountaineer_billing.__tests__ import conf_models as models
from mountaineer_billing.cli.main import billing_sync
from mountaineer_billing.cli.sync_down import StripeSyncDown
from mountaineer_billing.cli.sync_down_reporter import RichSyncDownReporter
from mountaineer_billing.cli.sync_up import (
    INTERNAL_FREQUENCY_KEY,
    INTERNAL_PRICE_ID_KEY,
    INTERNAL_PRODUCT_ID_KEY,
)
from mountaineer_billing.enums import PriceBillingInterval, SyncStatus


class FakeListResponse:
    def __init__(self, objects: list[object]):
        self._objects = objects

    def auto_paging_iter(self):
        return iter(self._objects)


def build_customer(*, customer_id: str = "cus_test") -> stripe.Customer:
    return stripe.Customer.construct_from(
        {
            "object": "customer",
            "id": customer_id,
            "created": 1,
            "livemode": False,
        },
        key="test_stripe_key",
    )


def build_price(*, stripe_price_id: str = "price_test") -> stripe.Price:
    return stripe.Price.construct_from(
        {
            "object": "price",
            "id": stripe_price_id,
            "active": True,
            "billing_scheme": "per_unit",
            "created": 1,
            "currency": "usd",
            "livemode": False,
            "metadata": {
                INTERNAL_PRODUCT_ID_KEY: str(models.ProductID.SUBSCRIPTION_GOLD),
                INTERNAL_PRICE_ID_KEY: str(models.PriceID.DEFAULT),
                INTERNAL_FREQUENCY_KEY: PriceBillingInterval.MONTH.value,
            },
            "product": "prod_test",
            "type": "one_time",
        },
        key="test_stripe_key",
    )


def build_product() -> stripe.Product:
    return stripe.Product.construct_from(
        {
            "object": "product",
            "id": "prod_test",
            "active": True,
            "created": 1,
            "images": [],
            "livemode": False,
            "marketing_features": [],
            "metadata": {},
            "name": "Test Product",
            "updated": 2,
        },
        key="test_stripe_key",
    )


def build_subscription() -> stripe.Subscription:
    return stripe.Subscription.construct_from(
        {
            "object": "subscription",
            "id": "sub_test",
            "automatic_tax": {"enabled": False},
            "billing_cycle_anchor": 1,
            "billing_mode": {"type": "flexible"},
            "cancel_at_period_end": False,
            "collection_method": "charge_automatically",
            "created": 1,
            "currency": "usd",
            "customer": "cus_test",
            "discounts": [],
            "invoice_settings": {"issuer": {"type": "self"}},
            "items": {
                "object": "list",
                "data": [],
                "has_more": False,
                "url": "/v1/subscription_items?subscription=sub_test",
            },
            "livemode": False,
            "metadata": {},
            "start_date": 1,
            "status": "active",
        },
        key="test_stripe_key",
    )


@pytest.mark.asyncio
async def test_sync_down_persists_supported_objects_and_price_mappings(
    config: models.AppConfig,
    db_connection: DBConnection,
) -> None:
    with (
        patch("stripe.Charge.list", return_value=FakeListResponse([])),
        patch(
            "stripe.checkout.Session.list",
            return_value=FakeListResponse([]),
        ),
        patch(
            "stripe.Customer.list", return_value=FakeListResponse([build_customer()])
        ),
        patch("stripe.Invoice.list", return_value=FakeListResponse([])),
        patch("stripe.PaymentIntent.list", return_value=FakeListResponse([])),
        patch(
            "stripe.Price.list",
            side_effect=[
                FakeListResponse([build_price()]),
                FakeListResponse([]),
            ],
        ),
        patch("stripe.Product.list", return_value=FakeListResponse([build_product()])),
        patch(
            "stripe.Subscription.list",
            return_value=FakeListResponse([build_subscription()]),
        ),
        patch(
            "mountaineer_billing.cli.sync_down.MaterializeSubscriptions.run",
            new=AsyncMock(return_value=None),
        ) as mock_materialize,
    ):
        summary = await StripeSyncDown(config=config).sync_objects(db_connection)

    assert summary.synced_counts["customer"] == 1
    assert summary.synced_counts["price"] == 1
    assert summary.synced_counts["product"] == 1
    assert summary.synced_counts["subscription"] == 1
    assert summary.price_mappings_upserted == 1
    assert summary.customers_enqueued == 1
    assert summary.customers_materialized == 1
    mock_materialize.assert_awaited_once_with(
        stripe_customer_id="cus_test",
        _blocking=False,
    )

    stripe_objects = await db_connection.exec(select(models.StripeObject))
    assert len(stripe_objects) == 4
    assert {stripe_object.object_type for stripe_object in stripe_objects} == {
        "customer",
        "price",
        "product",
        "subscription",
    }

    product_prices = await db_connection.exec(select(models.ProductPrice))
    assert len(product_prices) == 1
    assert product_prices[0].stripe_price_id == "price_test"


@pytest.mark.asyncio
async def test_sync_down_updates_existing_rows_without_duplicates(
    config: models.AppConfig,
    db_connection: DBConnection,
) -> None:
    await db_connection.insert(
        [
            models.StripeObject(
                stripe_id="prod_test",
                object_type="product",
                generic_payload={"stale": True},
                sync_status=SyncStatus.PENDING,
            ),
            models.ProductPrice(
                product_id=models.ProductID.SUBSCRIPTION_GOLD,
                price_id=models.PriceID.DEFAULT,
                frequency=PriceBillingInterval.MONTH,
                stripe_price_id="price_old",
            ),
        ]
    )

    with (
        patch("stripe.Charge.list", return_value=FakeListResponse([])),
        patch(
            "stripe.checkout.Session.list",
            return_value=FakeListResponse([]),
        ),
        patch("stripe.Customer.list", return_value=FakeListResponse([])),
        patch("stripe.Invoice.list", return_value=FakeListResponse([])),
        patch("stripe.PaymentIntent.list", return_value=FakeListResponse([])),
        patch(
            "stripe.Price.list",
            side_effect=[
                FakeListResponse([build_price()]),
                FakeListResponse([]),
            ],
        ),
        patch("stripe.Product.list", return_value=FakeListResponse([build_product()])),
        patch("stripe.Subscription.list", return_value=FakeListResponse([])),
        patch(
            "mountaineer_billing.cli.sync_down.MaterializeSubscriptions.run",
            new=AsyncMock(return_value=None),
        ),
    ):
        await StripeSyncDown(config=config).sync_objects(db_connection)

    saved_products = await db_connection.exec(
        select(models.StripeObject).where(models.StripeObject.stripe_id == "prod_test")
    )
    assert len(saved_products) == 1
    assert saved_products[0].sync_status == SyncStatus.CLEAN
    assert saved_products[0].product is not None
    assert saved_products[0].product["name"] == "Test Product"

    product_prices = await db_connection.exec(
        select(models.ProductPrice).where(
            models.ProductPrice.product_id == models.ProductID.SUBSCRIPTION_GOLD,
            models.ProductPrice.price_id == models.PriceID.DEFAULT,
        )
    )
    assert len(product_prices) == 1
    assert product_prices[0].stripe_price_id == "price_test"


@pytest.mark.asyncio
async def test_sync_down_logs_progress_with_throughput_only(
    config: models.AppConfig,
    db_connection: DBConnection,
) -> None:
    sync_down = StripeSyncDown(config=config)
    sync_down.progress_log_interval_objects = 2
    sync_down.progress_log_interval_seconds = 3600

    with (
        patch("stripe.Charge.list", return_value=FakeListResponse([])),
        patch(
            "stripe.checkout.Session.list",
            return_value=FakeListResponse([]),
        ),
        patch(
            "stripe.Customer.list",
            return_value=FakeListResponse(
                [
                    build_customer(customer_id="cus_one"),
                    build_customer(customer_id="cus_two"),
                ]
            ),
        ),
        patch("stripe.Invoice.list", return_value=FakeListResponse([])),
        patch("stripe.PaymentIntent.list", return_value=FakeListResponse([])),
        patch(
            "stripe.Price.list",
            side_effect=[FakeListResponse([]), FakeListResponse([])],
        ),
        patch("stripe.Product.list", return_value=FakeListResponse([])),
        patch("stripe.Subscription.list", return_value=FakeListResponse([])),
        patch(
            "mountaineer_billing.cli.sync_down.MaterializeSubscriptions.run",
            new=AsyncMock(return_value="workflow-instance-id"),
        ),
        patch("mountaineer_billing.cli.sync_down_reporter.LOGGER.info") as mock_info,
    ):
        await sync_down.sync_objects(db_connection)

    rendered_messages = [
        call.args[0] % call.args[1:] if len(call.args) > 1 else call.args[0]
        for call in mock_info.call_args_list
    ]
    assert any(
        "Stripe customer sync progress: 2 objects synced" in message
        and "objects/sec" in message
        for message in rendered_messages
    )
    assert not any("ETA" in message for message in rendered_messages)


def test_rich_sync_down_reporter_renders_terminal_progress() -> None:
    output = StringIO()
    console = Console(file=output, force_terminal=False, width=120)

    with RichSyncDownReporter(console=console) as reporter:
        reporter.start_sync(api_version="2026-03-25.dahlia")
        reporter.start_endpoint(object_type="charge")
        reporter.update_endpoint(
            object_type="charge",
            synced_count=500,
            elapsed_seconds=10.0,
            objects_per_second=50.0,
        )
        reporter.complete_endpoint(
            object_type="charge",
            synced_count=500,
            elapsed_seconds=10.0,
            objects_per_second=50.0,
        )
        reporter.queue_materialization(customer_count=3)
        reporter.complete_sync(
            elapsed_seconds=12.0,
            total_synced=500,
            price_mappings_upserted=2,
            customers_enqueued=3,
        )

    rendered = output.getvalue()
    assert "Stripe sync down using API version 2026-03-25.dahlia" in rendered
    assert "charge" in rendered
    assert "500 synced" in rendered
    assert "50.0 /s" in rendered
    assert "Queueing subscription materialization for 3 customers" in rendered
    assert "Stripe sync down complete in 12s" in rendered


def test_sync_down_command_invokes_batch_driver_with_rich_reporter(
    config: models.AppConfig,
) -> None:
    fake_db_connection = object()
    batch_driver = Mock()
    batch_driver.sync_objects = AsyncMock(return_value=None)
    reporter_context = MagicMock()
    fake_reporter = object()
    reporter_context.__enter__.return_value = fake_reporter
    reporter_context.__exit__.return_value = None

    async def mock_run_with_db_connection(*, config, handler):
        return await handler(fake_db_connection)

    with (
        patch(
            "mountaineer_billing.cli.main.load_sync_config",
            return_value=config,
        ) as mock_load_config,
        patch(
            "mountaineer_billing.cli.main.run_with_db_connection",
            new=AsyncMock(side_effect=mock_run_with_db_connection),
        ) as mock_run_with_db,
        patch(
            "mountaineer_billing.cli.main.StripeSyncDown",
            return_value=batch_driver,
        ) as mock_batch_driver,
        patch(
            "mountaineer_billing.cli.main.RichSyncDownReporter",
            return_value=reporter_context,
        ) as mock_reporter_cls,
    ):
        result = CliRunner().invoke(
            billing_sync,
            ["down", "--config", "example.config:AppConfig"],
        )

    assert result.exit_code == 0
    mock_load_config.assert_called_once_with("example.config:AppConfig")
    mock_batch_driver.assert_called_once_with(config=config)
    batch_driver.sync_objects.assert_awaited_once_with(
        fake_db_connection,
        reporter=fake_reporter,
    )
    mock_reporter_cls.assert_called_once_with()
    mock_run_with_db.assert_awaited_once()
