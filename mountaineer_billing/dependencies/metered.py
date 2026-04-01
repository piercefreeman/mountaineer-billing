from contextlib import asynccontextmanager
from datetime import datetime, timezone

import asyncpg
from fastapi import Depends
from iceaxe import DBConnection
from iceaxe.mountaineer import DatabaseConfig

from mountaineer.dependencies import CoreDependencies
from mountaineer_auth import AuthDependencies

from mountaineer_billing import models
from mountaineer_billing.config import BillingConfig
from mountaineer_billing.dependencies.allocation import (
    CapacityAllocation,
    get_user_allocation_metered,
)
from mountaineer_billing.dependencies.usage import get_user_metered_usage
from mountaineer_billing.exceptions import ResourceExhausted
from mountaineer_billing.metered import metered_atomic_increase
from mountaineer_billing.products import (
    MeteredIDBase,
)


def verify_capacity(
    metered_type: MeteredIDBase,
    quantity_required: int = 1,
):
    def dependency(
        countdown_allocation: dict[MeteredIDBase, CapacityAllocation] = Depends(
            get_user_allocation_metered
        ),
        metered_usage: dict[MeteredIDBase, float] = Depends(get_user_metered_usage),
    ):
        # We refactor into different dependencies that are then called by this one - allows for the caching of resources if these are chained (and just generally allows for async await gathering of results)
        countdown_limit = countdown_allocation.get(metered_type, CapacityAllocation())
        usage = metered_usage.get(metered_type, 0)

        if usage + quantity_required > countdown_limit.total:
            raise ResourceExhausted(f"User has exceeded their {metered_type} limit")

        return True

    return dependency


@asynccontextmanager
async def new_database_session(config: DatabaseConfig):
    conn = await asyncpg.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
        database=config.POSTGRES_DB,
    )
    try:
        yield DBConnection(conn)
    finally:
        await conn.close()


def record_metered_usage(
    metered_id: MeteredIDBase,
    add_value: int,
):
    """
    Records an initial metered usage for a user when the function is called. If the function
    call fails, we will undo the metered usage record.

    Upsert a MeteredRecord into the database. If no record exists for the given record type
    and record date, will create a new one. Otherwise will update the current one in-place
    Note that this logic will hold a new transaction open for as long as the client function
    is running.

    """

    async def dependency(
        user: models.UserBillingMixin = Depends(AuthDependencies.require_valid_user),
        countdown_allocation: dict[MeteredIDBase, CapacityAllocation] = Depends(
            get_user_allocation_metered
        ),
        config: BillingConfig = Depends(
            CoreDependencies.get_config_with_type(BillingConfig)
        ),
        db_config: DatabaseConfig = Depends(
            CoreDependencies.get_config_with_type(DatabaseConfig)
        ),
    ):
        # Use a separate connection from any that the user may be leveraging, since we need
        # to keep a transaction open for the duration of the function call.
        async with new_database_session(db_config) as db_connection:
            metered_date = datetime.now(timezone.utc).date()

            # Where possible we want to draw down their subscription usage
            # before their one-off usage; since using one-off credits will be
            # permanent over time.
            countdown_limit = countdown_allocation.get(metered_id, CapacityAllocation())

            debit_variable = min(add_value, countdown_limit.variable)
            debit_perpetual = min(add_value - debit_variable, countdown_limit.perpetual)

            # Overflow shouldn't occur if we have validated the user's capacity first, but just
            # in case we rollover to the variable pricing
            overflow = add_value - countdown_limit.variable - countdown_limit.perpetual
            if overflow > 0:
                debit_variable += overflow

            debit_payload = [
                (debit_variable, False),
                (debit_perpetual, True),
            ]

            tx = db_connection.conn.transaction()
            await tx.start()

            try:
                for value, is_perpetual in debit_payload:
                    if value != 0:
                        await metered_atomic_increase(
                            user=user,
                            value=value,
                            metered_id=metered_id,
                            metered_date=metered_date,
                            is_perpetual=is_perpetual,
                            db_connection=db_connection,
                            config=config,
                        )

                yield True
                await tx.commit()
            except BaseException:
                # Rollback our initial increase
                await tx.rollback()

                raise

    return dependency
