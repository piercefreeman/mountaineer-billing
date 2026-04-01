from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
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
from mountaineer_billing.products import PriceIDBase, ProductIDBase


@dataclass(frozen=True)
class IntegrationRunSummary:
    checkout_url: str
    final_url: str
    video_path: Path | None


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


@click.command(name="integration-runner")
@async_to_sync
async def main() -> None:
    try:
        config = get_runner_config()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    selected_product_id, selected_price_id = _selected_checkout_product(config)
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
            slow_mo_ms=config.INTEGRATION_RUNNER_SLOW_MO_MS,
            timeout_ms=config.INTEGRATION_RUNNER_TIMEOUT_MS,
            pause_after_ms=config.INTEGRATION_RUNNER_PAUSE_AFTER_MS,
            submit=config.INTEGRATION_RUNNER_SUBMIT,
        )
        return IntegrationRunSummary(
            checkout_url=checkout_url,
            final_url=browser_result.final_url,
            video_path=browser_result.video_path,
        )

    summary = await run_with_db_connection(config=config, handler=handler)
    click.echo(f"Checkout URL: {summary.checkout_url}")
    click.echo(f"Final URL: {summary.final_url}")
    if summary.video_path is not None:
        click.echo(f"Video: {summary.video_path}")
