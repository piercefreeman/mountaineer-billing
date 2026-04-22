from __future__ import annotations

from collections.abc import Awaitable, Callable
from importlib import import_module
from inspect import Parameter, signature
from typing import Any, TypeGuard, TypeVar

import click
from iceaxe import DBConnection
from iceaxe.mountaineer import DatabaseConfig, DatabaseDependencies

from mountaineer import Depends
from mountaineer.config import (
    ConfigBase,
    get_config,
    register_config_in_context,
    unregister_config,
)
from mountaineer.dependencies import get_function_dependencies
from mountaineer.io import async_to_sync

from mountaineer_billing.cli.materialize import StripeSyncMaterialize
from mountaineer_billing.cli.sync_down import StripeSyncDown
from mountaineer_billing.cli.sync_down_reporter import RichSyncDownReporter
from mountaineer_billing.cli.sync_up import BillingSync
from mountaineer_billing.config import BillingConfig

ReturnValue = TypeVar("ReturnValue")


def sync_config_option(func: Callable[..., Any]) -> Callable[..., Any]:
    return click.option(
        "--config",
        "config_import_path",
        envvar="MOUNTAINEER_BILLING_CONFIG",
        help=(
            "Import path to your app config class, factory, or instance. "
            "Example: myapp.config:AppConfig"
        ),
    )(func)


def import_symbol(import_path: str) -> object:
    if ":" in import_path:
        module_path, symbol_name = import_path.split(":", 1)
    else:
        module_path, separator, symbol_name = import_path.rpartition(".")
        if not separator:
            raise click.UsageError(
                "Config import paths must look like module:AppConfig or module.AppConfig"
            )

    try:
        module = import_module(module_path)
    except ModuleNotFoundError as exc:
        raise click.UsageError(
            f"Could not import config module {module_path!r}"
        ) from exc

    try:
        return getattr(module, symbol_name)
    except AttributeError as exc:
        raise click.UsageError(
            f"Config symbol {symbol_name!r} was not found in module {module_path!r}"
        ) from exc


def is_zero_arg_factory(value: object) -> TypeGuard[Callable[[], object]]:
    if not callable(value):
        return False

    try:
        callable_signature = signature(value)
    except (TypeError, ValueError):
        return False

    for parameter in callable_signature.parameters.values():
        if (
            parameter.kind
            in {
                Parameter.POSITIONAL_ONLY,
                Parameter.POSITIONAL_OR_KEYWORD,
                Parameter.KEYWORD_ONLY,
            }
            and parameter.default is Parameter.empty
        ):
            return False

    return True


def require_mountaineer_config(config: BillingConfig) -> ConfigBase:
    if not isinstance(config, ConfigBase):
        raise click.UsageError(
            "Loaded config must also inherit from mountaineer.config.ConfigBase"
        )
    return config


def load_sync_config(config_import_path: str | None) -> BillingConfig:
    if config_import_path is None:
        try:
            raw_config = get_config()
        except ValueError as exc:
            raise click.UsageError(
                "Provide --config or set MOUNTAINEER_BILLING_CONFIG so billing-sync "
                "can load your application settings."
            ) from exc
    else:
        config_target = import_symbol(config_import_path)
        if isinstance(config_target, BillingConfig):
            raw_config = config_target
        else:
            unregister_config()
            if isinstance(config_target, type):
                raw_config = config_target()
            elif is_zero_arg_factory(config_target):
                raw_config = config_target()
            else:
                raise click.UsageError(
                    "The imported config target must be a BillingConfig instance, "
                    "class, or zero-argument factory."
                )

    if not isinstance(raw_config, BillingConfig):
        raise click.UsageError(
            f"Loaded config must inherit from BillingConfig, got {type(raw_config)!r}"
        )
    require_mountaineer_config(raw_config)
    if not isinstance(raw_config, DatabaseConfig):
        raise click.UsageError(
            "Loaded config must also inherit from iceaxe.mountaineer.DatabaseConfig"
        )

    return raw_config


async def run_with_db_connection(
    *,
    config: BillingConfig,
    handler: Callable[[DBConnection], Awaitable[ReturnValue]],
) -> ReturnValue:
    async def dependency_wrapper(
        db_connection: DBConnection = Depends(DatabaseDependencies.get_db_connection),
    ) -> ReturnValue:
        return await handler(db_connection)

    with register_config_in_context(require_mountaineer_config(config)):
        async with get_function_dependencies(callable=dependency_wrapper) as deps:
            return await dependency_wrapper(**deps)


@click.group(name="billing-sync")
def billing_sync() -> None:
    """Sync local billing state with Stripe."""


@click.group(name="stripe-sync")
def stripe_sync() -> None:
    """Run Stripe maintenance workflows against local billing state."""


@billing_sync.command("up")
@sync_config_option
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Calculate and log the Stripe catalog diff without applying changes.",
)
@async_to_sync
async def sync_up_command(
    *,
    config_import_path: str | None,
    dry_run: bool,
) -> None:
    config = load_sync_config(config_import_path)

    async def handler(db_connection: DBConnection) -> None:
        await BillingSync(config=config).sync_products(
            products=config.BILLING_PRODUCTS,
            db_connection=db_connection,
            dry_run=dry_run,
        )

    await run_with_db_connection(config=config, handler=handler)


@billing_sync.command("down")
@sync_config_option
@async_to_sync
async def sync_down_command(
    *,
    config_import_path: str | None,
) -> None:
    config = load_sync_config(config_import_path)

    async def handler(db_connection: DBConnection) -> None:
        with RichSyncDownReporter() as reporter:
            await StripeSyncDown(config=config).sync_objects(
                db_connection,
                reporter=reporter,
            )

    await run_with_db_connection(config=config, handler=handler)


@stripe_sync.command("materialize")
@sync_config_option
@async_to_sync
async def stripe_sync_materialize_command(
    *,
    config_import_path: str | None,
) -> None:
    config = load_sync_config(config_import_path)

    async def handler(db_connection: DBConnection) -> None:
        await StripeSyncMaterialize(config=config).materialize_users(db_connection)

    await run_with_db_connection(config=config, handler=handler)


__all__ = [
    "billing_sync",
    "load_sync_config",
    "run_with_db_connection",
    "stripe_sync",
    "stripe_sync_materialize_command",
    "sync_down_command",
    "sync_up_command",
]
