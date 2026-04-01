from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from iceaxe import DBConnection
from iceaxe.schemas.cli import create_all

from integration_runner.config import IntegrationRunnerConfig
from integration_runner.models import RUNNER_TABLE_MODELS
from mountaineer_billing.cli.main import run_with_db_connection
from mountaineer_billing.webhook import router

config = IntegrationRunnerConfig()


async def _ensure_schema() -> None:
    async def handler(db_connection: DBConnection) -> None:
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
