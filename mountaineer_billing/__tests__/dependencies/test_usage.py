from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Request
from freezegun import freeze_time
from iceaxe import DBConnection
from iceaxe.mountaineer import DatabaseDependencies
from pydantic import BaseModel

from mountaineer.dependencies import get_function_dependencies

from mountaineer_billing import dependencies as BillingDependencies
from mountaineer_billing.__tests__ import conf_models as models
from mountaineer_billing.dependencies.usage import (
    closest_billing_start,
    get_user_metered_usage_all_time,
    get_user_metered_usage_cycle,
)
from mountaineer_billing.products import MeteredDefinition, RollupType


@dataclass
class MeteredTestCaseDefinition:
    offset: timedelta
    metered_id: models.MeteredID
    current_usage: int


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metered_items, expected_usage",
    [
        (
            # Simple, rolling aggregate
            [
                MeteredTestCaseDefinition(
                    offset=timedelta(days=-30),
                    metered_id=models.MeteredID.ITEM_GENERATION,
                    current_usage=5,
                ),
                MeteredTestCaseDefinition(
                    offset=timedelta(days=-60),
                    metered_id=models.MeteredID.ITEM_GENERATION,
                    current_usage=10,
                ),
            ],
            # 15 items, continuous
            {
                models.MeteredID.ITEM_GENERATION: 15,
            },
        )
    ],
)
async def test_get_user_metered_usage_all_time(
    user: models.User,
    mock_request: Request,
    db_connection: DBConnection,
    metered_items: list[MeteredTestCaseDefinition],
    expected_usage: dict[models.MeteredID, float],
):
    await db_connection.insert(
        [
            models.MeteredUsage(
                metered_id=metered_item.metered_id,
                metered_usage=metered_item.current_usage,
                metered_date=(datetime.now(timezone.utc) + metered_item.offset).date(),
                user_id=user.id,
            )
            for metered_item in metered_items
        ]
    )

    async with get_function_dependencies(
        callable=get_user_metered_usage_all_time,
        request=mock_request,
        dependency_overrides={
            DatabaseDependencies.get_db_connection: lambda: db_connection,
        },
    ) as values:
        result = await get_user_metered_usage_all_time(**values)

    assert result == expected_usage


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resource_grant_date, metered_items, expected_usage",
    [
        (
            timedelta(days=-20),
            # Simple, rolling aggregate
            [
                MeteredTestCaseDefinition(
                    offset=timedelta(days=-15),
                    metered_id=models.MeteredID.ITEM_GENERATION,
                    current_usage=5,
                ),
                MeteredTestCaseDefinition(
                    offset=timedelta(days=-60),
                    metered_id=models.MeteredID.ITEM_GENERATION,
                    current_usage=10,
                ),
            ],
            # 5 items, only within this billing cycle
            {
                models.MeteredID.ITEM_GENERATION: 5,
            },
        ),
        # Should reset at the start of every month, even with yearly billing
        # where they have one subscription / resource grant for the whole year.
        # The -45 days should mean that we're 15 days into this current month cycle.
        (
            timedelta(days=-45),
            [
                MeteredTestCaseDefinition(
                    offset=timedelta(days=-15),
                    metered_id=models.MeteredID.ITEM_GENERATION,
                    current_usage=5,
                ),
                MeteredTestCaseDefinition(
                    offset=timedelta(days=-35),
                    metered_id=models.MeteredID.ITEM_GENERATION,
                    current_usage=10,
                ),
            ],
            {
                models.MeteredID.ITEM_GENERATION: 5,
            },
        ),
    ],
)
@freeze_time("2024-07-28")
async def test_get_user_metered_usage_cycle(
    user: models.User,
    mock_request: Request,
    db_connection: DBConnection,
    resource_grant_date: timedelta,
    metered_items: list[MeteredTestCaseDefinition],
    expected_usage: dict[models.MeteredID, float],
):
    # Assume the user has an active subscription
    resource_access_grant = models.ResourceAccess(
        started_datetime=datetime.now(timezone.utc) + resource_grant_date,
        is_perpetual=False,
        stripe_price_id=None,
        stripe_product_id=None,
        subscription_id=None,
        product_id=models.ProductID.SUBSCRIPTION_GOLD,
        user_id=user.id,
    )
    await db_connection.insert([resource_access_grant])

    await db_connection.insert(
        [
            models.MeteredUsage(
                metered_id=metered_item.metered_id,
                metered_usage=metered_item.current_usage,
                metered_date=(datetime.now(timezone.utc) + metered_item.offset).date(),
                user_id=user.id,
            )
            for metered_item in metered_items
        ]
    )

    async with get_function_dependencies(
        callable=get_user_metered_usage_cycle,
        request=mock_request,
        dependency_overrides={
            DatabaseDependencies.get_db_connection: lambda: db_connection,
        },
    ) as values:
        result = await get_user_metered_usage_cycle(**values)

    assert result == expected_usage


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rollup_type, expected_value",
    [
        (RollupType.AGGREGATE, 15.0),
        (RollupType.CURRENT_CYCLE, 5.0),
    ],
)
async def test_get_user_metered_usage(
    mock_request: Request,
    rollup_type: RollupType,
    expected_value: float,
):
    """
    Test that we correctly choose between the different types of rollups
    depending on the global config for the metered item.

    """

    # Technically not a configuration class, but we just need it to override
    # our BILLING_METERED object in the same way
    class MockConfig(BaseModel):
        BILLING_METERED: dict[models.MeteredID, MeteredDefinition] = {
            models.MeteredID.ITEM_GENERATION: MeteredDefinition(
                usage_rollup=rollup_type,
            )
        }

    config = MockConfig()

    async with get_function_dependencies(
        callable=BillingDependencies.get_user_metered_usage,
        request=mock_request,
        dependency_overrides={
            get_user_metered_usage_cycle: lambda: {
                models.MeteredID.ITEM_GENERATION: 5,
            },
            get_user_metered_usage_all_time: lambda: {
                models.MeteredID.ITEM_GENERATION: 15,
            },
        },
    ) as values:
        result = BillingDependencies.get_user_metered_usage(
            **{
                **values,
                # Must be overridden here instead of in the dependency_overrides
                # since get_config_with_type() is a dynamic generator function
                # whose signature will change
                "config": config,  # type: ignore
            }
        )

    assert result == {models.MeteredID.ITEM_GENERATION: expected_value}


@pytest.mark.parametrize(
    "original_payment_date, simulated_today, expected_result",
    [
        # Standard cases
        (datetime(2023, 1, 15), datetime(2023, 8, 7), datetime(2023, 7, 15)),
        (datetime(2023, 1, 1), datetime(2023, 8, 1), datetime(2023, 8, 1)),
        (datetime(2023, 1, 31), datetime(2023, 8, 5), datetime(2023, 7, 31)),
        (datetime(2023, 1, 15), datetime(2023, 1, 15), datetime(2023, 1, 15)),
        (datetime(2023, 1, 1), datetime(2024, 3, 1), datetime(2024, 3, 1)),
        # Non-leap year February
        (datetime(2023, 1, 30), datetime(2023, 3, 5), datetime(2023, 2, 28)),
        # Leap year February
        (datetime(2023, 1, 29), datetime(2024, 3, 5), datetime(2024, 2, 29)),
        # Was assigned on the 30th now it's Feb. The month previous clock
        # is still running until the last day of the month.
        (datetime(2023, 1, 30), datetime(2023, 2, 27), datetime(2023, 1, 30)),
        (datetime(2023, 1, 30), datetime(2023, 2, 28), datetime(2023, 2, 28)),
    ],
)
def test_closest_billing_start(
    original_payment_date: datetime,
    simulated_today: datetime,
    expected_result: datetime,
):
    with freeze_time(simulated_today):
        result = closest_billing_start(original_payment_date)
        assert result == expected_result
