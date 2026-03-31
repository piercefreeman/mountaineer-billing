from datetime import date, datetime, timedelta

import pytest
from iceaxe import DBConnection

from mountaineer_billing.__tests__ import conf_models as models
from mountaineer_billing.metered import metered_atomic_increase


@pytest.mark.parametrize(
    "metered_id, metered_date, current_value, new_value, expected_value",
    [
        # Test for new record (should create new record)
        (models.MeteredID.ITEM_GENERATION, datetime.now().date(), None, 200, 200),
        # Test for existing record (should increment existing record)
        (
            models.MeteredID.ITEM_GENERATION,
            datetime.now().date() - timedelta(days=1),
            100,
            100,
            200,
        ),
    ],
)
@pytest.mark.asyncio
async def test_metered_atomic_increment(
    metered_id: models.MeteredID,
    metered_date: date,
    current_value: int | None,
    new_value: int,
    expected_value: int | Exception,
    db_connection: DBConnection,
    user: models.User,
    config: models.AppConfig,
):
    if current_value is not None:
        metered_record = models.MeteredUsage(
            metered_id=metered_id,
            metered_date=metered_date,
            user_id=user.id,
            metered_usage=current_value,
        )
        await db_connection.insert([metered_record])

    result = await metered_atomic_increase(
        user=user,
        value=new_value,
        metered_id=metered_id,
        metered_date=metered_date,
        is_perpetual=False,
        db_connection=db_connection,
        config=config,
    )
    assert result == expected_value
