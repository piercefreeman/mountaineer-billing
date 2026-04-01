from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
from dotenv import load_dotenv
from iceaxe import DBConnection, select
from iceaxe.mountaineer import DatabaseDependencies
from iceaxe.schemas.cli import create_all

from mountaineer.dependencies import get_function_dependencies
from mountaineer.io import async_to_sync
from mountaineer_auth import AuthDependencies

from integration_runner.browser import (
    BrowserRunResult,
    CardDetails,
    run_checkout_browser,
)
from integration_runner.config import IntegrationRunnerConfig, get_runner_config
from integration_runner.models import RUNNER_TABLE_MODELS, User
from mountaineer_billing import BillingDependencies
from mountaineer_billing.cli.main import run_with_db_connection
from mountaineer_billing.cli.sync_up import BillingSync
from mountaineer_billing.config import BillingConfig
from mountaineer_billing.enums import PriceBillingInterval, SyncStatus
from mountaineer_billing.products import PriceIDBase, ProductIDBase


@dataclass(frozen=True)
class IntegrationRunSummary:
    checkout_url: str
    final_url: str
    video_path: Path | None
    billing_summary: "MaterializedBillingSummary"


@dataclass(frozen=True)
class MaterializedBillingSummary:
    stripe_customer_id: str
    stripe_object_count: int
    stripe_object_types: tuple[str, ...]
    checkout_session_count: int
    subscription_count: int
    resource_access_count: int
    payment_count: int
    projection_status: SyncStatus


@dataclass(frozen=True)
class ObservedBillingState:
    stripe_customer_id: str | None
    stripe_object_count: int
    stripe_object_types: tuple[str, ...]
    clean_stripe_object_types: tuple[str, ...]
    checkout_session_count: int
    subscription_count: int
    resource_access_count: int
    payment_count: int
    projection_statuses: tuple[SyncStatus, ...]


def _resolve_checkout_selection(
    *,
    config: BillingConfig,
    product_id: str,
    price_id: str,
) -> tuple[ProductIDBase, PriceIDBase]:
    for product in config.BILLING_PRODUCTS:
        if str(product.id) != product_id:
            continue

        for price in product.prices:
            if str(price.id) == price_id:
                return product.id, price.id

        available_prices = ", ".join(sorted(str(price.id) for price in product.prices))
        raise click.UsageError(
            f"Unknown price id {price_id!r} for product {product_id!r}. "
            f"Available price ids: {available_prices}"
        )

    available_products = ", ".join(
        sorted(str(product.id) for product in config.BILLING_PRODUCTS)
    )
    raise click.UsageError(
        f"Unknown product id {product_id!r}. Available product ids: {available_products}"
    )


async def _ensure_local_schema(
    db_connection: DBConnection,
) -> None:
    await create_all(db_connection, models=RUNNER_TABLE_MODELS)


async def _reset_local_schema(
    db_connection: DBConnection,
) -> None:
    await db_connection.conn.execute(
        """
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
        END $$;
    """
    )

    await db_connection.conn.execute(
        """
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN (
                SELECT typname
                FROM pg_type
                WHERE typtype = 'e'
                AND typnamespace = (
                    SELECT oid
                    FROM pg_namespace
                    WHERE nspname = 'public'
                )
            ) LOOP
                EXECUTE 'DROP TYPE IF EXISTS ' || quote_ident(r.typname) || ' CASCADE';
            END LOOP;
        END $$;
    """
    )


class AutoApproveBillingSync(BillingSync):
    async def _confirm_changes(self, sync_diff) -> bool:  # type: ignore[override]
        return True


async def _sync_products_to_test_stripe(
    *,
    config: IntegrationRunnerConfig,
    db_connection: DBConnection,
) -> None:
    await AutoApproveBillingSync(config=config).sync_products(
        products=config.BILLING_PRODUCTS,
        db_connection=db_connection,
    )


async def _ensure_checkout_user(
    *,
    config: IntegrationRunnerConfig,
    db_connection: DBConnection,
) -> User:
    user_model = config.BILLING_MODELS.USER
    users = await db_connection.exec(
        select(user_model).where(
            user_model.email == config.INTEGRATION_RUNNER_USER_EMAIL
        )
    )
    user = users[0] if users else None
    if user is not None:
        return user

    user = user_model(
        email=config.INTEGRATION_RUNNER_USER_EMAIL,
        hashed_password=user_model.get_password_hash(
            config.INTEGRATION_RUNNER_USER_PASSWORD
        ),
        full_name=config.INTEGRATION_RUNNER_FULL_NAME,
    )
    await db_connection.insert([user])
    return user


def _selected_checkout_product(
    config: IntegrationRunnerConfig,
) -> tuple[ProductIDBase, PriceIDBase]:
    return _resolve_checkout_selection(
        config=config,
        product_id=str(config.INTEGRATION_RUNNER_PRODUCT_ID),
        price_id=str(config.INTEGRATION_RUNNER_PRICE_ID),
    )


def _selected_checkout_frequency(
    config: IntegrationRunnerConfig,
) -> PriceBillingInterval:
    for product in config.BILLING_PRODUCTS:
        if product.id != config.INTEGRATION_RUNNER_PRODUCT_ID:
            continue

        for price in product.prices:
            if price.id == config.INTEGRATION_RUNNER_PRICE_ID:
                return price.frequency

    raise click.UsageError(
        "Could not determine the billing frequency for the selected integration "
        "runner product and price."
    )


def _expects_subscription_projection(
    frequency: PriceBillingInterval,
) -> bool:
    return frequency != PriceBillingInterval.ONETIME


async def _build_checkout_url(
    *,
    db_connection: DBConnection,
    user: Any,
    products: list[tuple[ProductIDBase, PriceIDBase]],
    success_url: str,
    cancel_url: str,
    allow_promotion_codes: bool,
) -> str:
    async with get_function_dependencies(
        callable=BillingDependencies.checkout_builder,
        dependency_overrides={
            DatabaseDependencies.get_db_connection: lambda: db_connection,
            AuthDependencies.require_valid_user: lambda: user,
        },
    ) as values:
        build_checkout = BillingDependencies.checkout_builder(**values)

    return await build_checkout(
        products=products,
        success_url=success_url,
        cancel_url=cancel_url,
        allow_promotion_codes=allow_promotion_codes,
    )


async def _load_billing_state(
    *,
    config: IntegrationRunnerConfig,
    db_connection: DBConnection,
    user_id: Any,
) -> ObservedBillingState:
    users = await db_connection.exec(
        select(config.BILLING_MODELS.USER).where(
            config.BILLING_MODELS.USER.id == user_id
        )
    )
    user = users[0] if users else None
    stripe_customer_id = user.stripe_customer_id if user is not None else None

    if stripe_customer_id is None:
        return ObservedBillingState(
            stripe_customer_id=None,
            stripe_object_count=0,
            stripe_object_types=(),
            clean_stripe_object_types=(),
            checkout_session_count=0,
            subscription_count=0,
            resource_access_count=0,
            payment_count=0,
            projection_statuses=(),
        )

    stripe_objects = await db_connection.exec(
        select(config.BILLING_MODELS.STRIPE_OBJECT).where(
            config.BILLING_MODELS.STRIPE_OBJECT.stripe_customer_id == stripe_customer_id
        )
    )
    checkout_sessions = await db_connection.exec(
        select(config.BILLING_MODELS.CHECKOUT_SESSION).where(
            config.BILLING_MODELS.CHECKOUT_SESSION.user_id == user_id
        )
    )
    subscriptions = await db_connection.exec(
        select(config.BILLING_MODELS.SUBSCRIPTION).where(
            config.BILLING_MODELS.SUBSCRIPTION.user_id == user_id
        )
    )
    resource_access = await db_connection.exec(
        select(config.BILLING_MODELS.RESOURCE_ACCESS).where(
            config.BILLING_MODELS.RESOURCE_ACCESS.user_id == user_id
        )
    )
    payments = await db_connection.exec(
        select(config.BILLING_MODELS.PAYMENT).where(
            config.BILLING_MODELS.PAYMENT.user_id == user_id
        )
    )
    projection_states = await db_connection.exec(
        select(config.BILLING_MODELS.PROJECTION_STATE).where(
            config.BILLING_MODELS.PROJECTION_STATE.stripe_customer_id
            == stripe_customer_id
        )
    )

    stripe_object_types = tuple(
        sorted({stripe_object.object_type for stripe_object in stripe_objects})
    )
    clean_stripe_object_types = tuple(
        sorted(
            {
                stripe_object.object_type
                for stripe_object in stripe_objects
                if stripe_object.sync_status == SyncStatus.CLEAN
            }
        )
    )
    projection_statuses = tuple(
        sorted(
            (
                projection_state.projection_status
                for projection_state in projection_states
            ),
            key=str,
        )
    )

    return ObservedBillingState(
        stripe_customer_id=stripe_customer_id,
        stripe_object_count=len(stripe_objects),
        stripe_object_types=stripe_object_types,
        clean_stripe_object_types=clean_stripe_object_types,
        checkout_session_count=len(checkout_sessions),
        subscription_count=len(subscriptions),
        resource_access_count=len(resource_access),
        payment_count=len(payments),
        projection_statuses=projection_statuses,
    )


def _billing_state_errors(
    state: ObservedBillingState,
    *,
    expect_subscription: bool,
) -> list[str]:
    errors: list[str] = []
    if state.stripe_customer_id is None:
        errors.append("user.stripe_customer_id is still null")
        return errors

    if state.stripe_object_count == 0:
        errors.append("no StripeObject rows have been materialized")

    if "checkout.session" not in state.clean_stripe_object_types:
        errors.append("checkout.session is missing from clean StripeObject rows")

    if state.checkout_session_count < 1:
        errors.append("no CheckoutSession rows were projected")

    if state.resource_access_count < 1:
        errors.append("no ResourceAccess rows were projected")

    if state.payment_count < 1:
        errors.append("no Payment rows were projected")

    if SyncStatus.CLEAN not in state.projection_statuses:
        errors.append("BillingProjectionState is not clean yet")

    if expect_subscription:
        if "subscription" not in state.clean_stripe_object_types:
            errors.append("subscription is missing from clean StripeObject rows")
        if state.subscription_count < 1:
            errors.append("no Subscription rows were projected")

    return errors


def _format_billing_state(state: ObservedBillingState) -> str:
    return (
        f"stripe_customer_id={state.stripe_customer_id!r}, "
        f"stripe_object_count={state.stripe_object_count}, "
        f"stripe_object_types={list(state.stripe_object_types)}, "
        f"clean_stripe_object_types={list(state.clean_stripe_object_types)}, "
        f"checkout_session_count={state.checkout_session_count}, "
        f"subscription_count={state.subscription_count}, "
        f"resource_access_count={state.resource_access_count}, "
        f"payment_count={state.payment_count}, "
        f"projection_statuses={[str(status) for status in state.projection_statuses]}"
    )


async def _wait_for_materialized_billing_state(
    *,
    config: IntegrationRunnerConfig,
    db_connection: DBConnection,
    user_id: Any,
    expect_subscription: bool,
) -> MaterializedBillingSummary:
    timeout_seconds = config.INTEGRATION_RUNNER_POST_CHECKOUT_TIMEOUT_MS / 1000
    poll_interval_seconds = (
        config.INTEGRATION_RUNNER_POST_CHECKOUT_POLL_INTERVAL_MS / 1000
    )
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    last_state = await _load_billing_state(
        config=config,
        db_connection=db_connection,
        user_id=user_id,
    )

    while True:
        errors = _billing_state_errors(
            last_state,
            expect_subscription=expect_subscription,
        )
        if not errors:
            assert last_state.stripe_customer_id is not None
            assert SyncStatus.CLEAN in last_state.projection_statuses
            return MaterializedBillingSummary(
                stripe_customer_id=last_state.stripe_customer_id,
                stripe_object_count=last_state.stripe_object_count,
                stripe_object_types=last_state.clean_stripe_object_types,
                checkout_session_count=last_state.checkout_session_count,
                subscription_count=last_state.subscription_count,
                resource_access_count=last_state.resource_access_count,
                payment_count=last_state.payment_count,
                projection_status=SyncStatus.CLEAN,
            )

        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError(
                "Timed out waiting for the checkout flow to materialize billing "
                f"state. Pending conditions: {errors}. "
                f"Last observed state: {_format_billing_state(last_state)}"
            )

        await asyncio.sleep(poll_interval_seconds)
        last_state = await _load_billing_state(
            config=config,
            db_connection=db_connection,
            user_id=user_id,
        )


@click.command(name="integration-runner")
@async_to_sync
async def main() -> None:
    load_dotenv()

    try:
        config = get_runner_config()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    selected_product_id, selected_price_id = _selected_checkout_product(config)
    selected_frequency = _selected_checkout_frequency(config)
    resolved_video_dir = Path(config.INTEGRATION_RUNNER_VIDEO_DIR).resolve()

    async def handler(db_connection: DBConnection) -> IntegrationRunSummary:
        await _reset_local_schema(db_connection)
        await _ensure_local_schema(db_connection)
        await _sync_products_to_test_stripe(
            config=config,
            db_connection=db_connection,
        )
        user = await _ensure_checkout_user(
            config=config,
            db_connection=db_connection,
        )
        checkout_url = await _build_checkout_url(
            db_connection=db_connection,
            user=user,
            products=[
                (selected_product_id, selected_price_id),
            ],
            success_url=config.INTEGRATION_RUNNER_SUCCESS_URL,
            cancel_url=config.INTEGRATION_RUNNER_CANCEL_URL,
            allow_promotion_codes=config.INTEGRATION_RUNNER_ALLOW_PROMOTION_CODES,
        )
        browser_result: BrowserRunResult = await run_checkout_browser(
            checkout_url=checkout_url,
            card=CardDetails(
                email=user.email,
                number=config.INTEGRATION_RUNNER_CARD_NUMBER,
                expiry=config.INTEGRATION_RUNNER_CARD_EXPIRY,
                cvc=config.INTEGRATION_RUNNER_CARD_CVC,
                cardholder_name=config.INTEGRATION_RUNNER_CARDHOLDER_NAME,
                postal_code=config.INTEGRATION_RUNNER_POSTAL_CODE,
            ),
            video_dir=resolved_video_dir,
            success_url=config.INTEGRATION_RUNNER_SUCCESS_URL,
            cancel_url=config.INTEGRATION_RUNNER_CANCEL_URL,
            slow_mo_ms=config.INTEGRATION_RUNNER_SLOW_MO_MS,
            timeout_ms=config.INTEGRATION_RUNNER_TIMEOUT_MS,
            pause_after_ms=config.INTEGRATION_RUNNER_PAUSE_AFTER_MS,
            submit=config.INTEGRATION_RUNNER_SUBMIT,
            uncheck_save_information=config.INTEGRATION_RUNNER_UNCHECK_SAVE_INFORMATION,
        )
        billing_summary = await _wait_for_materialized_billing_state(
            config=config,
            db_connection=db_connection,
            user_id=user.id,
            expect_subscription=_expects_subscription_projection(selected_frequency),
        )
        return IntegrationRunSummary(
            checkout_url=checkout_url,
            final_url=browser_result.final_url,
            video_path=browser_result.video_path,
            billing_summary=billing_summary,
        )

    summary = await run_with_db_connection(config=config, handler=handler)
    click.echo(f"Checkout URL: {summary.checkout_url}")
    click.echo(f"Final URL: {summary.final_url}")
    click.echo(f"Stripe Customer ID: {summary.billing_summary.stripe_customer_id}")
    click.echo(
        "Stripe Object Types: " + ", ".join(summary.billing_summary.stripe_object_types)
    )
    click.echo(f"Checkout Sessions: {summary.billing_summary.checkout_session_count}")
    click.echo(f"Subscriptions: {summary.billing_summary.subscription_count}")
    click.echo(f"Resource Access Rows: {summary.billing_summary.resource_access_count}")
    click.echo(f"Payments: {summary.billing_summary.payment_count}")
    click.echo(f"Projection Status: {summary.billing_summary.projection_status}")
    if summary.video_path is not None:
        click.echo(f"Video: {summary.video_path}")
