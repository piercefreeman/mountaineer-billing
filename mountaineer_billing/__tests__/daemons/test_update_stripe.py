from datetime import datetime, timedelta, timezone
from json import loads as json_loads
from unittest.mock import MagicMock, patch

import pytest
import stripe
from iceaxe import DBConnection, select
from waymark import provide_dependencies

from mountaineer_billing import StripeWebhookType
from mountaineer_billing.__tests__ import conf_models as models
from mountaineer_billing.__tests__.conf_models import AppConfig, PriceID, ProductID
from mountaineer_billing.__tests__.fixtures import get_fixtures_path
from mountaineer_billing.daemons.update_stripe import (
    CompleteCheckoutSessionRequest,
    CreateSubscriptionRequest,
    UpdateSubscriptionRequest,
    complete_checkout_session,
    create_subscription,
    update_subscription,
)
from mountaineer_billing.enums import PriceBillingInterval, StripeStatus
from mountaineer_billing.logging import LOGGER


def get_stripe_events(package_name: str):
    events = get_fixtures_path(f"stripe_flows/{package_name}").glob("*.json")
    paths = [(path.name.split("_")[0], path) for path in events]
    for _, path in sorted(paths, key=lambda x: int(x[0])):
        if ".extra." in str(path):
            continue
        LOGGER.debug(f"Processing stripe event path: {path}")
        yield json_loads(path.read_text())


@pytest.fixture
def mock_checkout_session_item_list(config: AppConfig):
    line_items_path = get_fixtures_path(
        "stripe_flows/subscription/4_checkout.session.completed.extra.line_items.json"
    )
    results = [
        stripe.LineItem.construct_from(item, config.STRIPE_API_KEY)
        for item in json_loads(line_items_path.read_text())["data"]
    ]
    with patch(
        "stripe.checkout.Session.list_line_items"
    ) as mocked_checkout_session_list:
        mocked_checkout_session_list.return_value = results
        yield mocked_checkout_session_list


@pytest.mark.asyncio
async def test_new_stripe_subscription(
    db_connection: DBConnection,
    config: AppConfig,
    mock_checkout_session_item_list: MagicMock,
):
    user = models.User(
        # Grabbed from the fixtures, should be created and set
        # before the checkout flow begins
        stripe_customer_id="cus_SKXENLZtmfAcAK",
        email="test@example.com",
        hashed_password="",
    )
    await db_connection.insert([user])

    # Simulate a sync that already occurred
    product_price = models.ProductPrice(
        stripe_price_id="price_1RPpoIRGAudMahWRkfjEf4xl",
        product_id=ProductID.SUBSCRIPTION_GOLD,
        frequency=PriceBillingInterval.MONTH,
        price_id=PriceID.DEFAULT,
    )
    await db_connection.insert([product_price])

    for payload in get_stripe_events("subscription"):
        try:
            payload_type = StripeWebhookType(payload["type"])
        except ValueError:
            LOGGER.debug(f"No established webhook for: {payload['type']}")
            continue

        LOGGER.debug(f"Processing payload: {payload_type}")

        # Route to the correct action based on type
        if payload_type in {
            StripeWebhookType.SUBSCRIPTION_CANCELED,
            StripeWebhookType.SUBSCRIPTION_UPDATED,
        }:
            async with provide_dependencies(
                update_subscription,
                {
                    "request": UpdateSubscriptionRequest(payload=payload),
                    "config": config,
                    "db_connection": db_connection,
                },
            ) as deps:
                await update_subscription(**deps)
        elif payload_type == StripeWebhookType.SUBSCRIPTION_CREATED:
            async with provide_dependencies(
                create_subscription,
                {
                    "request": CreateSubscriptionRequest(payload=payload),
                    "config": config,
                    "db_connection": db_connection,
                },
            ) as deps:
                await create_subscription(**deps)
        elif payload_type == StripeWebhookType.CHECKOUT_SESSION_COMPLETE:
            async with provide_dependencies(
                complete_checkout_session,
                {
                    "request": CompleteCheckoutSessionRequest(payload=payload),
                    "config": config,
                    "db_connection": db_connection,
                },
            ) as deps:
                await complete_checkout_session(**deps)

    # Test the impact
    # At this point we expect the user to have a valid subscription
    # and an access grant to this resource
    mock_checkout_session_item_list.assert_called_once()

    subscription_query = select(models.Subscription).where(
        models.Subscription.user_id == user.id
    )
    subscriptions = await db_connection.exec(subscription_query)
    assert len(subscriptions) == 1

    subscription = subscriptions[0]
    assert subscription.stripe_status == StripeStatus.ACTIVE
    assert subscription.stripe_current_period_start
    assert subscription.stripe_current_period_end == (
        subscription.stripe_current_period_start + timedelta(days=31)
    )

    resource_query = select(models.ResourceAccess).where(
        models.ResourceAccess.user_id == user.id
    )
    resources = await db_connection.exec(resource_query)
    assert len(resources) == 1

    resource = resources[0]
    assert resource.product_id == ProductID.SUBSCRIPTION_GOLD
    assert resource.subscription_id == subscription.id
    assert resource.started_datetime
    assert not resource.ended_datetime


@pytest.mark.asyncio
async def test_new_stripe_oneoff(
    db_connection: DBConnection,
    config: AppConfig,
    mock_checkout_session_item_list: MagicMock,
):
    user = models.User(
        # Grabbed from the fixtures, should be created and set
        # before the checkout flow begins
        stripe_customer_id="cus_SKXFxw9dIHhkS4",
        email="test@example.com",
        hashed_password="",
    )
    await db_connection.insert([user])

    # Simulate a sync that already occurred
    product_price = models.ProductPrice(
        stripe_price_id="price_1RPpoIRGAudMahWRkfjEf4xl",
        product_id=ProductID.ONEOFF_50_ITEMS,
        frequency=PriceBillingInterval.ONETIME,
        price_id=PriceID.DEFAULT,
    )
    await db_connection.insert([product_price])

    for payload in get_stripe_events("one_time"):
        try:
            payload_type = StripeWebhookType(payload["type"])
        except ValueError:
            LOGGER.debug(f"No established webhook for: {payload['type']}")
            continue

        # Route to the correct action based on type
        if payload_type in {
            StripeWebhookType.SUBSCRIPTION_CANCELED,
            StripeWebhookType.SUBSCRIPTION_UPDATED,
        }:
            async with provide_dependencies(
                update_subscription,
                {
                    "request": UpdateSubscriptionRequest(payload=payload),
                    "config": config,
                    "db_connection": db_connection,
                },
            ) as deps:
                await update_subscription(**deps)
        elif payload_type == StripeWebhookType.SUBSCRIPTION_CREATED:
            async with provide_dependencies(
                create_subscription,
                {
                    "request": CreateSubscriptionRequest(payload=payload),
                    "config": config,
                    "db_connection": db_connection,
                },
            ) as deps:
                await create_subscription(**deps)
        elif payload_type == StripeWebhookType.CHECKOUT_SESSION_COMPLETE:
            async with provide_dependencies(
                complete_checkout_session,
                {
                    "request": CompleteCheckoutSessionRequest(payload=payload),
                    "config": config,
                    "db_connection": db_connection,
                },
            ) as deps:
                await complete_checkout_session(**deps)

    # Test the impact
    # At this point we expect the user to not have a subscription and instead
    # to have a permanent access grant to this resource
    mock_checkout_session_item_list.assert_called_once()

    subscription_query = select(models.Subscription).where(
        models.Subscription.user_id == user.id
    )
    subscriptions = await db_connection.exec(subscription_query)
    assert len(subscriptions) == 0

    resource_query = select(models.ResourceAccess).where(
        models.ResourceAccess.user_id == user.id
    )
    resources = await db_connection.exec(resource_query)
    assert len(resources) == 1

    resource = resources[0]
    assert resource.product_id == ProductID.ONEOFF_50_ITEMS
    assert resource.is_perpetual
    assert not resource.subscription_id
    assert resource.started_datetime
    assert not resource.ended_datetime


@pytest.mark.asyncio
async def test_change_stripe_subscription(
    db_connection: DBConnection,
    config: AppConfig,
    mock_checkout_session_item_list: MagicMock,
):
    # Create a user with an existing subscription
    user = models.User(
        stripe_customer_id="cus_existing_customer",
        email="existing@example.com",
        hashed_password="",
    )
    await db_connection.insert([user])

    # Create an existing subscription
    existing_subscription = models.Subscription(
        user_id=user.id,
        stripe_subscription_id="sub_existing",
        stripe_status=StripeStatus.ACTIVE,
        stripe_current_period_start=datetime.now(timezone.utc),
        stripe_current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await db_connection.insert([existing_subscription])

    # Create existing product prices
    old_product_price = models.ProductPrice(
        stripe_price_id="price_old",
        product_id=ProductID.SUBSCRIPTION_SILVER,
        frequency=PriceBillingInterval.MONTH,
        price_id=PriceID.DEFAULT,
    )
    new_product_price = models.ProductPrice(
        stripe_price_id="price_new",
        product_id=ProductID.SUBSCRIPTION_GOLD,
        frequency=PriceBillingInterval.MONTH,
        price_id=PriceID.DEFAULT,
    )
    await db_connection.insert([old_product_price, new_product_price])

    # Create an existing resource access
    old_resource_access = models.ResourceAccess(
        user_id=user.id,
        subscription_id=existing_subscription.id,
        product_id=ProductID.SUBSCRIPTION_SILVER,
        started_datetime=datetime.now(timezone.utc),
        stripe_price_id="price_old",
        stripe_product_id="product_old",
    )
    await db_connection.insert([old_resource_access])

    # Simulate a subscription update event
    new_current_period_start = datetime.now(timezone.utc)
    new_current_period_end = new_current_period_start + timedelta(days=30)

    update_payload = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_existing",
                "customer": "cus_existing_customer",
                "status": "active",
                "ended_at": None,
                "items": {
                    "object": "list",
                    "data": [
                        {
                            "id": "item_existing",
                            "current_period_start": int(
                                new_current_period_start.timestamp()
                            ),
                            "current_period_end": int(
                                new_current_period_end.timestamp()
                            ),
                            "plan": {
                                "id": "price_new",
                            },
                        }
                    ],
                },
            }
        },
    }

    async with provide_dependencies(
        update_subscription,
        {
            "request": UpdateSubscriptionRequest(payload=update_payload),
            "config": config,
            "db_connection": db_connection,
        },
    ) as deps:
        await update_subscription(**deps)

    # Verify the subscription and resource access have been updated
    updated_subscription_query = select(models.Subscription).where(
        models.Subscription.id == existing_subscription.id
    )
    updated_subscriptions = await db_connection.exec(updated_subscription_query)
    updated_subscription = updated_subscriptions[0]

    updated_resource_query = select(models.ResourceAccess).where(
        models.ResourceAccess.id == old_resource_access.id
    )
    updated_resources = await db_connection.exec(updated_resource_query)
    updated_resource_access = updated_resources[0]

    assert updated_subscription
    assert updated_subscription.stripe_status == StripeStatus.ACTIVE
    assert updated_subscription.stripe_current_period_start
    assert updated_subscription.stripe_current_period_end

    assert updated_resource_access.product_id == ProductID.SUBSCRIPTION_GOLD
    assert updated_resource_access.subscription_id == updated_subscription.id
    assert updated_resource_access.started_datetime == new_current_period_start.replace(
        # Not sent through the API
        microsecond=0
    )
    assert not updated_resource_access.ended_datetime
