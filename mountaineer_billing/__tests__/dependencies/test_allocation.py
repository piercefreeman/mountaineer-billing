from datetime import date, datetime, timezone

import pytest
from fastapi import Request
from iceaxe import DBConnection
from iceaxe.mountaineer import DatabaseDependencies

from mountaineer.dependencies import get_function_dependencies
from mountaineer_auth import AuthDependencies

from mountaineer_billing import dependencies as BillingDependencies
from mountaineer_billing.__tests__ import conf_models as models
from mountaineer_billing.exceptions import ResourceExhausted


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "has_used, should_raise",
    [
        (49, False),
        (50, True),
        (51, True),
    ],
)
async def test_verify_capacity(
    user: models.User,
    mock_request: Request,
    db_connection: DBConnection,
    has_used: int,
    should_raise: bool,
):
    resource_access_grant = models.ResourceAccess(
        started_datetime=datetime.now(timezone.utc),
        is_perpetual=True,
        stripe_price_id=None,
        stripe_product_id=None,
        stripe_subscription_id=None,
        product_id=models.ProductID.ONEOFF_50_ITEMS,
        user_id=user.id,
    )
    await db_connection.insert([resource_access_grant])

    def echo_db_connection():
        return db_connection

    verify_fn = BillingDependencies.verify_capacity(models.MeteredID.ITEM_GENERATION)
    async with get_function_dependencies(
        callable=verify_fn,
        request=mock_request,
        dependency_overrides={
            DatabaseDependencies.get_db_connection: echo_db_connection,
            AuthDependencies.require_valid_user: lambda: user,
        },
    ) as values:
        assert verify_fn(**values)

    # If we use up the 50 items, we should no longer have capacity
    metered_usage = models.MeteredUsage(
        metered_id=models.MeteredID.ITEM_GENERATION,
        metered_usage=has_used,
        metered_date=date.today(),
        user_id=user.id,
    )
    await db_connection.insert([metered_usage])

    async with get_function_dependencies(
        callable=verify_fn,
        request=mock_request,
        dependency_overrides={
            DatabaseDependencies.get_db_connection: echo_db_connection,
            AuthDependencies.require_valid_user: lambda: user,
        },
    ) as values:
        if should_raise:
            with pytest.raises(ResourceExhausted):
                verify_fn(**values)
        else:
            verify_fn(**values)
