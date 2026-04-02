from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner
from iceaxe.base import DBModelMetaclass

from mountaineer.config import unregister_config

from mountaineer_billing.__tests__ import conf_models as models
from mountaineer_billing.enums import SyncStatus

RUNNER_PROJECT_ROOT = Path(__file__).resolve().parents[3] / "integration-runner"
if str(RUNNER_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNNER_PROJECT_ROOT))


@pytest.fixture(autouse=True)
def clear_registered_config() -> None:
    unregister_config()
    try:
        yield
    finally:
        DBModelMetaclass._registry = [
            model
            for model in DBModelMetaclass._registry
            if not getattr(model, "__module__", "").startswith("integration_runner.")
        ]
        DBModelMetaclass._cached_args = {
            model: args
            for model, args in DBModelMetaclass._cached_args.items()
            if not getattr(model, "__module__", "").startswith("integration_runner.")
        }
        unregister_config()


def test_integration_runner_command_creates_checkout_and_reports_video_path(
    config: models.AppConfig,
    user: models.User,
) -> None:
    BrowserRunResult = importlib.import_module(
        "integration_runner.browser"
    ).BrowserRunResult
    cli_module = importlib.import_module("integration_runner.cli")
    main = cli_module.main

    fake_db_connection = object()
    recorded_video = Path("/tmp/integration-runner/video.webm")
    runner_config = SimpleNamespace(
        BILLING_PRODUCTS=config.BILLING_PRODUCTS,
        INTEGRATION_RUNNER_PRODUCT_ID=models.ProductID.ONEOFF_50_ITEMS,
        INTEGRATION_RUNNER_PRICE_ID=models.PriceID.DEFAULT,
        INTEGRATION_RUNNER_SUCCESS_URL="https://example.com/billing/success",
        INTEGRATION_RUNNER_CANCEL_URL="https://example.com/billing/cancel",
        INTEGRATION_RUNNER_ALLOW_PROMOTION_CODES=False,
        INTEGRATION_RUNNER_CARD_NUMBER="4242424242424242",
        INTEGRATION_RUNNER_CARD_EXPIRY="1234",
        INTEGRATION_RUNNER_CARD_CVC="123",
        INTEGRATION_RUNNER_CARDHOLDER_NAME="Integration Runner",
        INTEGRATION_RUNNER_POSTAL_CODE="94107",
        INTEGRATION_RUNNER_VIDEO_DIR=Path("artifacts/test-videos"),
        INTEGRATION_RUNNER_SLOW_MO_MS=250,
        INTEGRATION_RUNNER_TIMEOUT_MS=30_000,
        INTEGRATION_RUNNER_PAUSE_AFTER_MS=5_000,
        INTEGRATION_RUNNER_SUBMIT=True,
        INTEGRATION_RUNNER_UNCHECK_SAVE_INFORMATION=True,
        INTEGRATION_RUNNER_POST_CHECKOUT_TIMEOUT_MS=60_000,
        INTEGRATION_RUNNER_POST_CHECKOUT_POLL_INTERVAL_MS=1_000,
    )
    billing_summary = cli_module.MaterializedBillingSummary(
        stripe_customer_id="cus_test",
        stripe_object_count=3,
        stripe_object_types=("checkout.session", "customer", "subscription"),
        checkout_session_count=1,
        subscription_count=1,
        resource_access_count=1,
        payment_count=1,
        projection_status=SyncStatus.CLEAN,
    )

    async def mock_run_with_db_connection(*, config, handler):
        return await handler(fake_db_connection)

    with (
        patch(
            "integration_runner.cli.get_runner_config",
            return_value=runner_config,
        ) as mock_get_runner_config,
        patch(
            "integration_runner.cli.run_with_db_connection",
            new=AsyncMock(side_effect=mock_run_with_db_connection),
        ) as mock_run_with_db_connection,
        patch(
            "integration_runner.cli._reset_local_schema",
            new=AsyncMock(return_value=None),
        ) as mock_reset_local_schema,
        patch(
            "integration_runner.cli._ensure_local_schema",
            new=AsyncMock(return_value=None),
        ) as mock_ensure_local_schema,
        patch(
            "integration_runner.cli._sync_products_to_test_stripe",
            new=AsyncMock(return_value=None),
        ) as mock_sync_products,
        patch(
            "integration_runner.cli._ensure_checkout_user",
            new=AsyncMock(return_value=user),
        ) as mock_ensure_checkout_user,
        patch(
            "integration_runner.cli._build_checkout_url",
            new=AsyncMock(return_value="https://example.com/checkout"),
        ) as mock_build_checkout_url,
        patch(
            "integration_runner.cli.run_checkout_browser",
            new=AsyncMock(
                return_value=BrowserRunResult(
                    final_url="https://example.com/billing/success",
                    video_path=recorded_video,
                )
            ),
        ) as mock_run_browser,
        patch(
            "integration_runner.cli._wait_for_materialized_billing_state",
            new=AsyncMock(return_value=billing_summary),
        ) as mock_wait_for_materialized_billing_state,
    ):
        result = CliRunner().invoke(main, [])

    assert result.exit_code == 0
    mock_get_runner_config.assert_called_once_with()
    mock_run_with_db_connection.assert_awaited_once()
    mock_reset_local_schema.assert_awaited_once_with(fake_db_connection)
    mock_ensure_local_schema.assert_awaited_once_with(fake_db_connection)
    mock_sync_products.assert_awaited_once_with(
        config=runner_config,
        db_connection=fake_db_connection,
    )
    mock_ensure_checkout_user.assert_awaited_once_with(
        config=runner_config,
        db_connection=fake_db_connection,
    )
    mock_build_checkout_url.assert_awaited_once()
    mock_run_browser.assert_awaited_once()
    mock_wait_for_materialized_billing_state.assert_awaited_once_with(
        config=runner_config,
        db_connection=fake_db_connection,
        user_id=user.id,
        expect_subscription=False,
    )
    assert "Checkout URL: https://example.com/checkout" in result.output
    assert "Final URL: https://example.com/billing/success" in result.output
    assert "Stripe Customer ID: cus_test" in result.output
    assert (
        "Stripe Object Types: checkout.session, customer, subscription" in result.output
    )
    assert "Checkout Sessions: 1" in result.output
    assert "Subscriptions: 1" in result.output
    assert "Resource Access Rows: 1" in result.output
    assert "Payments: 1" in result.output
    assert "Projection Status: clean" in result.output
    assert f"Video: {recorded_video}" in result.output


def test_integration_runner_command_rejects_unknown_product(
    config: models.AppConfig,
) -> None:
    main = importlib.import_module("integration_runner.cli").main

    runner_config = SimpleNamespace(
        BILLING_PRODUCTS=config.BILLING_PRODUCTS,
        INTEGRATION_RUNNER_PRODUCT_ID="DOES_NOT_EXIST",
        INTEGRATION_RUNNER_PRICE_ID=models.PriceID.DEFAULT,
    )

    with patch(
        "integration_runner.cli.get_runner_config",
        return_value=runner_config,
    ):
        result = CliRunner().invoke(main, [])

    assert result.exit_code != 0
    assert "Unknown product id" in result.output


def test_integration_runner_config_requires_test_stripe_key() -> None:
    IntegrationRunnerConfig = importlib.import_module(
        "integration_runner.config"
    ).IntegrationRunnerConfig

    with pytest.raises(ValueError, match="sk_test_"):
        IntegrationRunnerConfig(STRIPE_API_KEY="sk_live_123")


def test_billing_state_errors_require_subscription_rows_for_recurring_checkout() -> (
    None
):
    cli_module = importlib.import_module("integration_runner.cli")

    state = cli_module.ObservedBillingState(
        stripe_customer_id="cus_test",
        stripe_object_count=2,
        stripe_object_types=("checkout.session", "customer"),
        clean_stripe_object_types=("checkout.session", "customer"),
        checkout_session_count=1,
        subscription_count=0,
        resource_access_count=1,
        payment_count=1,
        projection_statuses=(SyncStatus.CLEAN,),
    )

    errors = cli_module._billing_state_errors(
        state,
        expect_subscription=True,
    )

    assert "subscription is missing from clean StripeObject rows" in errors
    assert "no Subscription rows were projected" in errors


@pytest.mark.asyncio
async def test_wait_for_materialized_billing_state_retries_until_sync_is_clean() -> (
    None
):
    cli_module = importlib.import_module("integration_runner.cli")

    pending_state = cli_module.ObservedBillingState(
        stripe_customer_id="cus_test",
        stripe_object_count=1,
        stripe_object_types=("customer",),
        clean_stripe_object_types=("customer",),
        checkout_session_count=0,
        subscription_count=0,
        resource_access_count=0,
        payment_count=0,
        projection_statuses=(SyncStatus.PENDING,),
    )
    materialized_state = cli_module.ObservedBillingState(
        stripe_customer_id="cus_test",
        stripe_object_count=3,
        stripe_object_types=("checkout.session", "customer", "subscription"),
        clean_stripe_object_types=("checkout.session", "customer", "subscription"),
        checkout_session_count=1,
        subscription_count=1,
        resource_access_count=1,
        payment_count=1,
        projection_statuses=(SyncStatus.CLEAN,),
    )
    config = SimpleNamespace(
        INTEGRATION_RUNNER_POST_CHECKOUT_TIMEOUT_MS=1_000,
        INTEGRATION_RUNNER_POST_CHECKOUT_POLL_INTERVAL_MS=0,
    )

    with (
        patch(
            "integration_runner.cli._load_billing_state",
            new=AsyncMock(side_effect=[pending_state, materialized_state]),
        ) as mock_load_billing_state,
        patch(
            "integration_runner.cli.asyncio.sleep",
            new=AsyncMock(return_value=None),
        ) as mock_sleep,
    ):
        summary = await cli_module._wait_for_materialized_billing_state(
            config=config,
            db_connection=object(),
            user_id="user_test",
            expect_subscription=True,
        )

    assert summary == cli_module.MaterializedBillingSummary(
        stripe_customer_id="cus_test",
        stripe_object_count=3,
        stripe_object_types=("checkout.session", "customer", "subscription"),
        checkout_session_count=1,
        subscription_count=1,
        resource_access_count=1,
        payment_count=1,
        projection_status=SyncStatus.CLEAN,
    )
    assert mock_load_billing_state.await_count == 2
    mock_sleep.assert_awaited_once_with(0.0)


@pytest.mark.asyncio
async def test_reset_local_schema_drops_tables_and_enum_types() -> None:
    reset_local_schema = importlib.import_module(
        "integration_runner.cli"
    )._reset_local_schema

    execute = AsyncMock()
    fake_db_connection = SimpleNamespace(conn=SimpleNamespace(execute=execute))

    await reset_local_schema(fake_db_connection)

    assert execute.await_count == 2
    table_reset_sql = execute.await_args_list[0].args[0]
    type_reset_sql = execute.await_args_list[1].args[0]
    assert "DROP TABLE IF EXISTS" in table_reset_sql
    assert '"billingprojectionstate"' in table_reset_sql
    assert '"workflow_versions"' not in table_reset_sql
    assert "DROP TYPE IF EXISTS" in type_reset_sql
    assert '"syncstatus"' in type_reset_sql
