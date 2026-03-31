from json import loads as json_loads
from unittest.mock import MagicMock, patch

import pytest
import stripe
from iceaxe import DBConnection, select
from waymark import provide_dependencies

from mountaineer_billing.__tests__ import conf_models as models
from mountaineer_billing.__tests__.conf_models import AppConfig, PriceID, ProductID
from mountaineer_billing.__tests__.fixtures import get_fixtures_path
from mountaineer_billing.daemons.ingest_stripe_event import (
    StoreStripeEventRequest,
    store_stripe_event,
)
from mountaineer_billing.daemons.project_stripe_billing import (
    ProjectBillingStateRequest,
    project_dirty_billing_states,
)
from mountaineer_billing.daemons.reconcile_stripe_objects import (
    ReconcileStripeObjectsRequest,
    reconcile_dirty_stripe_objects,
)
from mountaineer_billing.enums import PriceBillingInterval, StripeStatus, SyncStatus


def load_fixture(path: str) -> dict:
    return json_loads(get_fixtures_path(path).read_text())


@pytest.fixture
def mock_checkout_session_retrieve_and_lines(config: AppConfig):
    session_payload = load_fixture("stripe_flows/one_time/4_checkout.session.completed.json")[
        "data"
    ]["object"]
    line_items_payload = load_fixture(
        "stripe_flows/one_time/4_checkout.session.completed.extra.line_items.json"
    )["data"]

    with (
        patch("stripe.checkout.Session.retrieve") as mock_retrieve,
        patch("stripe.checkout.Session.list_line_items") as mock_list_line_items,
    ):
        mock_retrieve.return_value = stripe.checkout.Session.construct_from(
            session_payload,
            config.STRIPE_API_KEY,
        )
        mock_list_line_items.return_value = [
            stripe.LineItem.construct_from(item, config.STRIPE_API_KEY)
            for item in line_items_payload
        ]
        yield mock_retrieve, mock_list_line_items


@pytest.mark.asyncio
async def test_subscription_event_reconciles_and_projects(
    db_connection: DBConnection,
    config: AppConfig,
):
    user = models.User(
        stripe_customer_id="cus_SKXENLZtmfAcAK",
        email="test@example.com",
        hashed_password="",
    )
    await db_connection.insert([user])

    await db_connection.insert(
        [
            models.ProductPrice(
                stripe_price_id="price_1RPpoIRGAudMahWRkfjEf4xl",
                product_id=ProductID.SUBSCRIPTION_GOLD,
                frequency=PriceBillingInterval.MONTH,
                price_id=PriceID.DEFAULT,
            )
        ]
    )

    event_payload = load_fixture("stripe_flows/subscription/6_customer.subscription.created.json")
    subscription_payload = event_payload["data"]["object"]

    with patch("stripe.Subscription.retrieve") as mock_retrieve:
        mock_retrieve.return_value = stripe.Subscription.construct_from(
            subscription_payload,
            config.STRIPE_API_KEY,
        )

        async with provide_dependencies(
            store_stripe_event,
            {
                "request": StoreStripeEventRequest(payload=event_payload),
                "config": config,
                "db_connection": db_connection,
            },
        ) as deps:
            await store_stripe_event(**deps)

        async with provide_dependencies(
            reconcile_dirty_stripe_objects,
            {
                "request": ReconcileStripeObjectsRequest(limit=10),
                "config": config,
                "db_connection": db_connection,
            },
        ) as deps:
            reconcile_result = await reconcile_dirty_stripe_objects(**deps)

        async with provide_dependencies(
            project_dirty_billing_states,
            {
                "request": ProjectBillingStateRequest(limit=10),
                "config": config,
                "db_connection": db_connection,
            },
        ) as deps:
            projection_result = await project_dirty_billing_states(**deps)

    assert reconcile_result.processed_count == 1
    assert projection_result.projected_count == 1
    mock_retrieve.assert_called_once()

    events = await db_connection.exec(select(models.StripeEvent))
    assert len(events) == 1
    assert events[0].stripe_event_id == event_payload["id"]

    stripe_objects = await db_connection.exec(select(models.StripeObject))
    stripe_objects_by_type = {
        stripe_object.object_type: stripe_object for stripe_object in stripe_objects
    }
    assert "subscription" in stripe_objects_by_type
    assert stripe_objects_by_type["subscription"].stripe_id == subscription_payload["id"]
    assert stripe_objects_by_type["subscription"].sync_status == SyncStatus.CLEAN

    projection_states = await db_connection.exec(select(models.BillingProjectionState))
    assert len(projection_states) == 1
    assert projection_states[0].projection_status == SyncStatus.CLEAN

    subscriptions = await db_connection.exec(select(models.Subscription))
    assert len(subscriptions) == 1
    assert subscriptions[0].stripe_subscription_id == subscription_payload["id"]
    assert subscriptions[0].stripe_status == StripeStatus(subscription_payload["status"])

    resources = await db_connection.exec(select(models.ResourceAccess))
    assert len(resources) == 1
    assert resources[0].product_id == ProductID.SUBSCRIPTION_GOLD
    assert resources[0].subscription_id == subscriptions[0].id
    assert not resources[0].is_perpetual


@pytest.mark.asyncio
async def test_checkout_session_projects_one_time_payment_and_access(
    db_connection: DBConnection,
    config: AppConfig,
    mock_checkout_session_retrieve_and_lines: tuple[MagicMock, MagicMock],
):
    user = models.User(
        stripe_customer_id="cus_SKXFxw9dIHhkS4",
        email="test@example.com",
        hashed_password="",
    )
    await db_connection.insert([user])

    await db_connection.insert(
        [
            models.ProductPrice(
                stripe_price_id="price_1RPs8ZRGAudMahWRPpKlesnE",
                product_id=ProductID.ONEOFF_50_ITEMS,
                frequency=PriceBillingInterval.ONETIME,
                price_id=PriceID.DEFAULT,
            )
        ]
    )

    event_payload = load_fixture("stripe_flows/one_time/4_checkout.session.completed.json")

    async with provide_dependencies(
        store_stripe_event,
        {
            "request": StoreStripeEventRequest(payload=event_payload),
            "config": config,
            "db_connection": db_connection,
        },
    ) as deps:
        await store_stripe_event(**deps)

    async with provide_dependencies(
        reconcile_dirty_stripe_objects,
        {
            "request": ReconcileStripeObjectsRequest(limit=10),
            "config": config,
            "db_connection": db_connection,
        },
    ) as deps:
        reconcile_result = await reconcile_dirty_stripe_objects(**deps)

    async with provide_dependencies(
        project_dirty_billing_states,
        {
            "request": ProjectBillingStateRequest(limit=10),
            "config": config,
            "db_connection": db_connection,
        },
    ) as deps:
        projection_result = await project_dirty_billing_states(**deps)

    assert reconcile_result.processed_count == 1
    assert projection_result.projected_count == 1

    checkout_sessions = await db_connection.exec(select(models.CheckoutSession))
    assert len(checkout_sessions) == 1
    assert (
        checkout_sessions[0].stripe_checkout_session_id
        == event_payload["data"]["object"]["id"]
    )

    resources = await db_connection.exec(select(models.ResourceAccess))
    assert len(resources) == 1
    assert resources[0].product_id == ProductID.ONEOFF_50_ITEMS
    assert resources[0].is_perpetual

    payments = await db_connection.exec(select(models.Payment))
    assert len(payments) == 1
    assert payments[0].stripe_price_id == "price_1RPs8ZRGAudMahWRPpKlesnE"
    assert payments[0].stripe_customer_id == "cus_SKXFxw9dIHhkS4"


@pytest.mark.asyncio
async def test_duplicate_event_is_idempotent(
    db_connection: DBConnection,
    config: AppConfig,
    mock_checkout_session_retrieve_and_lines: tuple[MagicMock, MagicMock],
):
    user = models.User(
        stripe_customer_id="cus_SKXFxw9dIHhkS4",
        email="test@example.com",
        hashed_password="",
    )
    await db_connection.insert([user])

    await db_connection.insert(
        [
            models.ProductPrice(
                stripe_price_id="price_1RPs8ZRGAudMahWRPpKlesnE",
                product_id=ProductID.ONEOFF_50_ITEMS,
                frequency=PriceBillingInterval.ONETIME,
                price_id=PriceID.DEFAULT,
            )
        ]
    )

    event_payload = load_fixture("stripe_flows/one_time/4_checkout.session.completed.json")

    for _ in range(2):
        async with provide_dependencies(
            store_stripe_event,
            {
                "request": StoreStripeEventRequest(payload=event_payload),
                "config": config,
                "db_connection": db_connection,
            },
        ) as deps:
            await store_stripe_event(**deps)

    async with provide_dependencies(
        reconcile_dirty_stripe_objects,
        {
            "request": ReconcileStripeObjectsRequest(limit=10),
            "config": config,
            "db_connection": db_connection,
        },
    ) as deps:
        await reconcile_dirty_stripe_objects(**deps)

    async with provide_dependencies(
        project_dirty_billing_states,
        {
            "request": ProjectBillingStateRequest(limit=10),
            "config": config,
            "db_connection": db_connection,
        },
    ) as deps:
        await project_dirty_billing_states(**deps)

    events = await db_connection.exec(select(models.StripeEvent))
    assert len(events) == 1

    stripe_objects = await db_connection.exec(select(models.StripeObject))
    stripe_objects_by_type = {
        stripe_object.object_type: stripe_object for stripe_object in stripe_objects
    }
    assert "checkout.session" in stripe_objects_by_type

    payments = await db_connection.exec(select(models.Payment))
    assert len(payments) == 1

    resources = await db_connection.exec(select(models.ResourceAccess))
    assert len(resources) == 1
