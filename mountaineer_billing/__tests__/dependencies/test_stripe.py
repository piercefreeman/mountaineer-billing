from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import stripe
from fastapi import Request
from iceaxe import DBConnection
from iceaxe.mountaineer import DatabaseDependencies

from mountaineer.dependencies import get_function_dependencies
from mountaineer_auth import AuthDependencies

from mountaineer_billing import dependencies as BillingDependencies
from mountaineer_billing.__tests__ import conf_models as models
from mountaineer_billing.enums import PriceBillingInterval, StripeStatus


@pytest.mark.asyncio
async def test_checkout_builder(
    user: models.User,
    mock_request: Request,
    config: models.AppConfig,
    db_connection: DBConnection,
):
    # Make sure our prices have equivalent database objects with a stripe-id assigned
    product_price = models.ProductPrice(
        stripe_price_id="test_price_1",
        product_id=models.ProductID.ONEOFF_50_ITEMS,
        frequency=PriceBillingInterval.ONETIME,
        price_id=models.PriceID.DEFAULT,
    )
    await db_connection.insert([product_price])

    with (
        patch("stripe.Customer.create") as mocked_customer,
        patch("stripe.checkout.Session.create") as mocked_session,
    ):
        mocked_customer.return_value = stripe.Customer.construct_from(
            {
                "id": "cus_PcG7pNgMcOVbra",
            },
            key="TEST_KEY",
        )
        mocked_session.return_value = stripe.checkout.Session.construct_from(
            {
                "url": "TEST_URL",
            },
            key="TEST_KEY",
        )

        async with get_function_dependencies(
            callable=BillingDependencies.checkout_builder,
            request=mock_request,
            dependency_overrides={
                DatabaseDependencies.get_db_connection: lambda: db_connection,
            },
        ) as values:
            build_checkout = BillingDependencies.checkout_builder(**values)

        checkout_url = await build_checkout(
            products=[
                (models.ProductID.ONEOFF_50_ITEMS, models.PriceID.DEFAULT),
            ],
            success_url="http://localhost:8000/success",
            cancel_url="http://localhost:8000/cancel",
        )
        assert checkout_url == "TEST_URL"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stripe_status, expected_subscription",
    [
        (StripeStatus.ACTIVE, True),
        (StripeStatus.TRIALING, True),
        (StripeStatus.UNPAID, True),
        (StripeStatus.CANCELED, False),
    ],
)
async def test_any_subscription(
    stripe_status: StripeStatus,
    expected_subscription: bool,
    mock_request: Request,
    user: models.User,
    db_connection: DBConnection,
):
    subscription = models.Subscription(
        stripe_subscription_id="sub_test_1",
        stripe_current_period_start=datetime.now(timezone.utc),
        stripe_current_period_end=datetime.now(timezone.utc),
        stripe_status=stripe_status,
        user_id=user.id,
    )
    await db_connection.insert([subscription])

    async with get_function_dependencies(
        callable=BillingDependencies.any_subscription,
        request=mock_request,
        dependency_overrides={
            DatabaseDependencies.get_db_connection: lambda: db_connection,
            AuthDependencies.require_valid_user: lambda: user,
        },
    ) as values:
        found_subscription = await BillingDependencies.any_subscription(**values)

    if expected_subscription:
        assert found_subscription
        assert found_subscription.id == subscription.id
    else:
        assert found_subscription is None
