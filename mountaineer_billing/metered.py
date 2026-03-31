from datetime import date, datetime, timezone
from uuid import uuid4

from iceaxe import DBConnection

from mountaineer_billing import models
from mountaineer_billing.config import BillingConfig
from mountaineer_billing.products import (
    MeteredIDBase,
)


async def metered_atomic_increase(
    *,
    user: models.UserBillingMixin,
    metered_id: MeteredIDBase,
    metered_date: date,
    value: int,
    is_perpetual: bool,
    db_connection: DBConnection,
    config: BillingConfig,
) -> int:
    updated_metered_usage = await db_connection.conn.fetch(
        f"""
        INSERT INTO "{config.BILLING_METERED_USAGE.get_table_name()}"
        (id, metered_id, metered_date, is_perpetual, user_id, metered_usage, synced_usage, created_at, updated_at)
        VALUES
        ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (metered_id, metered_date, is_perpetual, user_id)
        DO UPDATE SET metered_usage = "{config.BILLING_METERED_USAGE.get_table_name()}"."metered_usage" + $6
        RETURNING metered_usage
        """,
        uuid4(),
        metered_id,
        metered_date,
        is_perpetual,
        user.id,
        value,
        0,
        datetime.now(timezone.utc),
        datetime.now(timezone.utc),
    )

    return int(updated_metered_usage[0]["metered_usage"])
