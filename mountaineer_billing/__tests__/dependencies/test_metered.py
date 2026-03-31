from unittest.mock import patch

import asyncpg
import pytest
from fastapi import Request
from iceaxe import DBConnection, Field, TableBase, UniqueConstraint, select
from iceaxe.mountaineer import DatabaseDependencies

from mountaineer import Depends
from mountaineer.dependencies import get_function_dependencies
from mountaineer_auth import AuthDependencies

from mountaineer_billing.__tests__ import conf_models as models
from mountaineer_billing.dependencies.metered import (
    CapacityAllocation,
    get_user_allocation_metered,
    record_metered_usage,
)
from mountaineer_billing.metered import metered_atomic_increase


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "capacity_allocation, value, expected_variable_usage, expected_perpetual_usage",
    [
        # Only draw from perpetual
        (
            CapacityAllocation(perpetual=5, variable=0),
            2,
            0,
            2,
        ),
        # Only draw from variable
        (
            CapacityAllocation(perpetual=0, variable=5),
            2,
            2,
            0,
        ),
        # Prefer to draw from variable if there are credits in both
        (
            CapacityAllocation(perpetual=5, variable=5),
            2,
            2,
            0,
        ),
        # Draw from variable and then overflow to perpetual
        (
            CapacityAllocation(perpetual=5, variable=5),
            8,
            5,
            3,
        ),
        # Unexpected in practice but we allow users to go negative. We expect
        # negative values will draw from variable quota
        (
            CapacityAllocation(perpetual=5, variable=5),
            20,
            15,
            5,
        ),
        # Negative values should credit their account
        (
            CapacityAllocation(perpetual=5, variable=5),
            -20,
            # Allocation will only go to variable
            -20,
            # We won't actually log any perpetual usage
            0,
        ),
    ],
)
async def test_record_metered_usage(
    mock_request: Request,
    capacity_allocation: CapacityAllocation,
    value: int,
    expected_perpetual_usage: int,
    expected_variable_usage: int,
    user: models.User,
    db_connection: DBConnection,
):
    # The function call creates an inner dependency that
    # has to be evaluated
    dependency = record_metered_usage(
        metered_id=models.MeteredID.ITEM_GENERATION,
        add_value=value,
    )

    async with get_function_dependencies(
        callable=dependency,
        request=mock_request,
        dependency_overrides={
            AuthDependencies.require_valid_user: lambda: user,
            get_user_allocation_metered: lambda: {
                models.MeteredID.ITEM_GENERATION: capacity_allocation
            },
        },
    ) as values:
        async for _ in dependency(**values):
            pass

    # Retrieve the latest billed
    metered_usage_query = select(models.MeteredUsage)
    metered_usage = await db_connection.exec(metered_usage_query)

    perpetual_allocation = [usage for usage in metered_usage if usage.is_perpetual]
    variable_allocation = [usage for usage in metered_usage if not usage.is_perpetual]

    if expected_perpetual_usage:
        assert len(perpetual_allocation) == 1
        assert perpetual_allocation[0].metered_usage == expected_perpetual_usage
    else:
        assert len(perpetual_allocation) == 0

    if expected_variable_usage:
        assert len(variable_allocation) == 1
        assert variable_allocation[0].metered_usage == expected_variable_usage
    else:
        assert len(variable_allocation) == 0


class ConstraintUser(TableBase):
    """
    Create a database mock with a constraint that we can use to trigger
    a SQL rollback required error

    """

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)

    table_args = [UniqueConstraint(columns=["name"])]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "capacity_allocation, value, expected_variable_usage, expected_perpetual_usage, failure_type",
    [
        # User failure during yield
        (CapacityAllocation(perpetual=5, variable=5), 8, 0, 0, "user"),
        # Server failure on first debit (variable allocation)
        (CapacityAllocation(perpetual=5, variable=5), 8, 0, 0, "server_variable"),
        # Server failure on second debit (perpetual allocation)
        # Should rollback the successfully completed variable debit
        (CapacityAllocation(perpetual=5, variable=5), 8, 0, 0, "server_perpetual"),
        # User database failure invalidates the transaction
        (CapacityAllocation(perpetual=5, variable=5), 8, 0, 0, "user_db"),
    ],
)
async def test_record_metered_usage_failures(
    mock_request: Request,
    capacity_allocation: CapacityAllocation,
    value: int,
    expected_variable_usage: int,
    expected_perpetual_usage: int,
    failure_type: str,
    user: models.User,
    db_connection: DBConnection,
):
    """
    Test that we only roll-back the values that have been successfully
    debited in the case of a failure.

    """

    async def mock_metered_atomic_increase(*args, **kwargs):
        is_perpetual = kwargs.get("is_perpetual", False)
        if failure_type == "server_perpetual" and is_perpetual:
            raise ValueError("Server error on perpetual")
        elif failure_type == "server_variable" and not is_perpetual:
            raise ValueError("Server error on variable")
        # Run a real successful debit
        return await metered_atomic_increase(*args, **kwargs)

    with patch(
        "mountaineer_billing.dependencies.metered.metered_atomic_increase"
    ) as metered_atomic_increase_mock:
        metered_atomic_increase_mock.side_effect = mock_metered_atomic_increase

        async def mock_user_function(
            metered_usage: bool = Depends(
                record_metered_usage(
                    metered_id=models.MeteredID.ITEM_GENERATION,
                    add_value=value,
                )
            ),
            db_connection: DBConnection = Depends(
                DatabaseDependencies.get_db_connection
            ),
        ):
            if failure_type == "user":
                raise ValueError("User-induced failure, should cause rollback of debit")
            elif failure_type == "user_db":
                # Simulate a user database failure
                user1 = ConstraintUser(name="Alice")
                await db_connection.insert([user1])

                user2 = ConstraintUser(name="Alice")
                await db_connection.insert([user2])

        try:
            async with get_function_dependencies(
                callable=mock_user_function,
                request=mock_request,
                dependency_overrides={
                    AuthDependencies.require_valid_user: lambda: user,
                    get_user_allocation_metered: lambda: {
                        models.MeteredID.ITEM_GENERATION: capacity_allocation
                    },
                },
            ) as values:
                await mock_user_function(**values)

        except (ValueError, asyncpg.exceptions.UniqueViolationError):
            # Expected exceptions for failure scenarios
            pass

    # Retrieve the latest billed usage
    metered_usage_query = select(models.MeteredUsage)
    metered_usage = await db_connection.exec(metered_usage_query)
    perpetual_allocation = [
        usage.metered_usage for usage in metered_usage if usage.is_perpetual
    ]
    variable_allocation = [
        usage.metered_usage for usage in metered_usage if not usage.is_perpetual
    ]

    assert sum(perpetual_allocation or [0]) == expected_perpetual_usage
    assert sum(variable_allocation or [0]) == expected_variable_usage
