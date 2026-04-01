from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from iceaxe import DBConnection
from iceaxe.schemas.cli import create_all
from iceaxe.schemas.db_memory_serializer import DatabaseMemorySerializer
from iceaxe.schemas.db_stubs import DBType

from integration_runner.config import IntegrationRunnerConfig
from integration_runner.models import RUNNER_TABLE_MODELS
from mountaineer_billing.cli.main import run_with_db_connection
from mountaineer_billing.webhook import router

config = IntegrationRunnerConfig()

EXPECTED_TABLES = frozenset(model.get_table_name() for model in RUNNER_TABLE_MODELS)
EXPECTED_TYPES = frozenset(
    obj.name
    for obj, _ in DatabaseMemorySerializer().delegate(RUNNER_TABLE_MODELS)
    if isinstance(obj, DBType)
)


async def _existing_table_names(db_connection: DBConnection) -> set[str]:
    rows = await db_connection.conn.fetch(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        """
    )
    return {row["tablename"] for row in rows}


async def _existing_type_names(db_connection: DBConnection) -> set[str]:
    rows = await db_connection.conn.fetch(
        """
        SELECT typname
        FROM pg_type
        WHERE typtype = 'e'
        AND typnamespace = (
            SELECT oid
            FROM pg_namespace
            WHERE nspname = 'public'
        )
        """
    )
    return {row["typname"] for row in rows}


async def _ensure_schema() -> None:
    async def handler(db_connection: DBConnection) -> None:
        existing_tables = await _existing_table_names(db_connection)
        if EXPECTED_TABLES.issubset(existing_tables):
            return

        existing_types = await _existing_type_names(db_connection)
        existing_billing_tables = EXPECTED_TABLES & existing_tables
        existing_billing_types = EXPECTED_TYPES & existing_types
        if existing_billing_tables or existing_billing_types:
            missing_tables = sorted(EXPECTED_TABLES - existing_tables)
            missing_types = sorted(EXPECTED_TYPES - existing_types)
            raise RuntimeError(
                "Integration runner billing schema is partially initialized. "
                f"Existing tables: {sorted(existing_billing_tables)}. "
                f"Existing enum types: {sorted(existing_billing_types)}. "
                f"Missing tables: {missing_tables}. "
                f"Missing enum types: {missing_types}. "
                "Reset the integration database volume before retrying."
            )

        await create_all(db_connection, models=RUNNER_TABLE_MODELS)

    await run_with_db_connection(config=config, handler=handler)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await _ensure_schema()
    yield


app = FastAPI(
    title="Integration Runner Billing Webhook App",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/healthz")
async def healthcheck() -> dict[str, bool]:
    return {"ok": True}
