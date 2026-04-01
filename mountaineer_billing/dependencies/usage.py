from datetime import datetime

from fastapi import Depends
from iceaxe import DBConnection, and_, func, or_, select
from iceaxe.mountaineer import DatabaseDependencies

from mountaineer.dependencies import CoreDependencies
from mountaineer_auth import AuthDependencies

from mountaineer_billing import models
from mountaineer_billing.config import BillingConfig
from mountaineer_billing.dependencies.allocation import get_user_resources
from mountaineer_billing.products import (
    MeteredIDBase,
    RollupType,
)


def closest_billing_start(original_payment_date: datetime) -> datetime:
    """
    Given a payment date, returns the most recent billing start date to
    the current date. Returns the current date if a new billing cycle starts
    today.

    """
    today = datetime.now()
    billing_day = original_payment_date.day

    def get_last_valid_date(year: int, month: int, day: int) -> datetime:
        while True:
            try:
                return datetime(year, month, day)
            except ValueError:
                day -= 1

    # Handle the current month
    last_billing_start = get_last_valid_date(today.year, today.month, billing_day)

    if last_billing_start > today:
        # Handle the previous month
        if today.month == 1:
            last_billing_start = get_last_valid_date(today.year - 1, 12, billing_day)
        else:
            last_billing_start = get_last_valid_date(
                today.year, today.month - 1, billing_day
            )

    return last_billing_start


async def get_user_metered_usage_cycle(
    config: BillingConfig = Depends(
        CoreDependencies.get_config_with_type(BillingConfig)
    ),
    resources: list[models.ResourceAccess] = Depends(get_user_resources),
    db_connection: DBConnection = Depends(DatabaseDependencies.get_db_connection),
    user: models.UserBillingMixin = Depends(AuthDependencies.require_valid_user),
) -> dict[MeteredIDBase, int]:
    """
    Retrieves the current metered usage for the user in the current cycle.

    """

    # Determine how each metered type is aggregated, either limited to the current
    # billing cycle or across all billing cycles
    # We ALWAYS get the perpetual metered usage, since this indicates that the
    # user used up some one-off credits. One-off credits will always be returned
    # in the allocation so they need to be mirrored in the user's usage.
    relevant_date_windows: list[tuple[datetime, datetime | None]] = [
        (resource.started_datetime, resource.ended_datetime)
        for resource in resources
        if resource.started_datetime is not None
        and resource.ended_datetime is not None
        and not resource.is_perpetual
    ]

    # Workaround for year-based billing. Right now we just take the last month,
    # billed from the start of their cycle to the end of the month.
    # This is a temporary solution until we can implement a more robust solution
    relevant_date_windows += [
        (closest_billing_start(resource.started_datetime), None)
        for resource in resources
        if resource.started_datetime is not None
        and resource.ended_datetime is None
        and not resource.is_perpetual
    ]

    relevant_date_filters = []
    for start, end in relevant_date_windows:
        current_filter = [
            config.BILLING_MODELS.METERED_USAGE.metered_date >= start.date()
        ]
        if end is not None:
            current_filter.append(
                config.BILLING_MODELS.METERED_USAGE.metered_date <= end.date()
            )
        relevant_date_filters.append(and_(*current_filter))

    metered_query = (
        select(
            (
                config.BILLING_MODELS.METERED_USAGE.metered_id,
                func.sum(config.BILLING_MODELS.METERED_USAGE.metered_usage),
            )
        )
        .where(
            config.BILLING_MODELS.METERED_USAGE.user_id == user.id,
            or_(
                *relevant_date_filters,
                config.BILLING_MODELS.METERED_USAGE.is_perpetual == True,  # noqa: E712
            ),
        )
        .group_by(config.BILLING_MODELS.METERED_USAGE.metered_id)
    )

    metered_results = await db_connection.exec(metered_query)

    return {metered_id: total_usage for metered_id, total_usage in metered_results}


async def get_user_metered_usage_all_time(
    config: BillingConfig = Depends(
        CoreDependencies.get_config_with_type(BillingConfig)
    ),
    db_connection: DBConnection = Depends(DatabaseDependencies.get_db_connection),
    user: models.UserBillingMixin = Depends(AuthDependencies.require_valid_user),
) -> dict[MeteredIDBase, int]:
    """
    Retrieves the current metered usage for the user, across all metered types. We collect
    the total usage for all time, for use in aggregation queries.

    """
    metered_query = (
        select(
            (
                config.BILLING_MODELS.METERED_USAGE.metered_id,
                func.sum(config.BILLING_MODELS.METERED_USAGE.metered_usage),
            )
        )
        .where(
            config.BILLING_MODELS.METERED_USAGE.user_id == user.id,
        )
        .group_by(config.BILLING_MODELS.METERED_USAGE.metered_id)
    )

    metered_results = await db_connection.exec(metered_query)

    return {metered_id: total_usage for metered_id, total_usage in metered_results}


def get_user_metered_usage(
    config: BillingConfig = Depends(
        CoreDependencies.get_config_with_type(BillingConfig)
    ),
    cycle: dict[MeteredIDBase, int] = Depends(get_user_metered_usage_cycle),
    all_time: dict[MeteredIDBase, int] = Depends(get_user_metered_usage_all_time),
) -> dict[MeteredIDBase, int]:
    """
    Final rollup of the user's current usage, based on how we are supposed to roll up
    the given metered types.

    """
    metered_amount: dict[MeteredIDBase, int] = {}
    for metered_id, definition in config.BILLING_METERED.items():
        if definition.usage_rollup == RollupType.CURRENT_CYCLE:
            metered_amount[metered_id] = cycle.get(metered_id, 0)
        elif definition.usage_rollup == RollupType.AGGREGATE:
            metered_amount[metered_id] = all_time.get(metered_id, 0)
        else:
            raise ValueError(f"Unknown rollup type {definition.usage_rollup}")

    return metered_amount
