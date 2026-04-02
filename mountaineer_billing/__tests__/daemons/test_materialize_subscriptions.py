from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from importlib import import_module
from typing import Annotated
from uuid import uuid4

import pytest
from iceaxe import DBConnection, select
from pydantic import BaseModel

from mountaineer_billing.__tests__ import conf_models as models
from mountaineer_billing.daemons.materialize_subscriptions import (
    LoadMaterializationContextResponse,
    MaterializeSubscriptions,
    MaterializeSubscriptionsResponse,
    build_materialized_subscription_state,
)
from mountaineer_billing.enums import StripeStatus, SyncStatus
from mountaineer_billing.stripe.v2026_03_25_dahlia.models import (
    InvoiceModel,
    PriceModel,
    SubscriptionModel,
)
from mountaineer_billing.stripe.v2026_03_25_dahlia.models._internal import (
    BillingBillResourceInvoicingLinesParentsInvoiceLineItemParent,
    BillingBillResourceInvoicingLinesParentsInvoiceLineItemSubscriptionItemParent,
    BillingBillResourceInvoicingPricingPricing,
    BillingBillResourceInvoicingPricingPricingPriceDetails,
    InvoiceLineItemPeriod,
    LineItem,
    Lines,
)
from mountaineer_billing.stripe.v2026_03_25_dahlia.models.checkout import Session


def rebuild_versioned_model(model_type: type[BaseModel]) -> type[BaseModel]:
    model_module = import_module(model_type.__module__)
    internal_namespace: dict[str, object] = {}
    module_name = model_module.__name__
    try:
        internal_module = import_module(f"{module_name}._internal")
    except ModuleNotFoundError:
        package_name, _, _ = module_name.rpartition(".")
        internal_module = (
            import_module(f"{package_name}._internal") if package_name else None
        )
    if internal_module is not None:
        internal_namespace = dict(vars(internal_module))

    model_type.model_rebuild(
        _types_namespace={
            "Annotated": Annotated,
            **internal_namespace,
            **dict(vars(model_module)),
        },
        force=True,
        raise_errors=False,
    )
    return model_type


for versioned_model in (InvoiceModel, PriceModel, Session, SubscriptionModel):
    rebuild_versioned_model(versioned_model)


@pytest.mark.asyncio
async def test_build_materialized_subscription_state_supports_modern_invoice_shapes() -> (
    None
):
    user_id = uuid4()
    price = PriceModel.model_construct(
        id="price_test",
        product="prod_test",
        unit_amount=2999,
    )
    line_item = LineItem.model_construct(
        amount=2999,
        currency="usd",
        discountable=False,
        discounts=[],
        id="il_test",
        livemode=False,
        metadata={},
        object="line_item",
        parent=BillingBillResourceInvoicingLinesParentsInvoiceLineItemParent.model_construct(
            type="subscription_item_details",
            subscription_item_details=BillingBillResourceInvoicingLinesParentsInvoiceLineItemSubscriptionItemParent.model_construct(
                proration=False,
                subscription="sub_test",
                subscription_item="si_test",
            ),
        ),
        period=InvoiceLineItemPeriod.model_construct(start=1, end=2),
        pricing=BillingBillResourceInvoicingPricingPricing.model_construct(
            type="price_details",
            unit_amount_decimal=Decimal("2999"),
            price_details=BillingBillResourceInvoicingPricingPricingPriceDetails.model_construct(
                price=price,
                product="prod_test",
            ),
        ),
        quantity=1,
        subtotal=2999,
    )
    invoice = InvoiceModel.model_construct(
        id="in_test",
        amount_paid=2999,
        lines=Lines.model_construct(
            data=[line_item],
            has_more=False,
            object="list",
            url="/v1/invoices/in_test/lines",
        ),
        status="paid",
    )
    context = LoadMaterializationContextResponse.model_construct(
        stripe_customer_id="cus_test",
        user_id=user_id,
        checkout_sessions=[],
        invoices=[invoice],
        subscriptions=[],
        product_prices=[],
    )

    state = await build_materialized_subscription_state(context)

    assert len(state.payments) == 1
    assert state.payments[0].paid_amount == 2999
    assert state.payments[0].total_price_amount == 2999
    assert state.payments[0].stripe_customer_id == "cus_test"
    assert state.payments[0].stripe_invoice_id == "in_test"
    assert state.payments[0].stripe_price_id == "price_test"
    assert state.payments[0].stripe_subscription_id == "sub_test"


@pytest.mark.asyncio
async def test_build_materialized_subscription_state_uses_modern_unit_amount_for_price_ratio() -> (
    None
):
    user_id = uuid4()
    price = PriceModel.model_construct(
        id="price_test",
        product="prod_test",
        unit_amount=2000,
    )
    line_item = LineItem.model_construct(
        amount=3000,
        currency="usd",
        discountable=True,
        discounts=[],
        id="il_discounted",
        livemode=False,
        metadata={},
        object="line_item",
        parent=BillingBillResourceInvoicingLinesParentsInvoiceLineItemParent.model_construct(
            type="subscription_item_details",
            subscription_item_details=BillingBillResourceInvoicingLinesParentsInvoiceLineItemSubscriptionItemParent.model_construct(
                proration=False,
                subscription="sub_test",
                subscription_item="si_test",
            ),
        ),
        period=InvoiceLineItemPeriod.model_construct(start=1, end=2),
        pricing=BillingBillResourceInvoicingPricingPricing.model_construct(
            type="price_details",
            unit_amount_decimal=Decimal("2000"),
            price_details=BillingBillResourceInvoicingPricingPricingPriceDetails.model_construct(
                price=price,
                product="prod_test",
            ),
        ),
        quantity=2,
        subtotal=4000,
    )
    invoice = InvoiceModel.model_construct(
        id="in_discounted",
        amount_paid=3000,
        lines=Lines.model_construct(
            data=[line_item],
            has_more=False,
            object="list",
            url="/v1/invoices/in_discounted/lines",
        ),
        status="paid",
    )
    context = LoadMaterializationContextResponse.model_construct(
        stripe_customer_id="cus_test",
        user_id=user_id,
        checkout_sessions=[],
        invoices=[invoice],
        subscriptions=[],
        product_prices=[],
    )

    state = await build_materialized_subscription_state(context)

    assert len(state.payments) == 1
    assert state.payments[0].paid_amount == 3000
    assert state.payments[0].total_price_amount == 4000
    assert state.payments[0].price_ratio == pytest.approx(0.75)


@pytest.mark.asyncio
async def test_materialize_subscriptions_workflow_happy_path(
    db_connection: DBConnection,
    user: models.User,
) -> None:
    stripe_customer_id = "cus_materialize"
    price = PriceModel(
        object="price",
        id="price_test",
        active=True,
        billing_scheme="per_unit",
        created=1,
        currency="usd",
        livemode=False,
        metadata={},
        product="prod_test",
        type="one_time",
        unit_amount=2999,
    )
    checkout_session = Session(
        object="checkout.session",
        id="cs_test",
        amount_subtotal=2999,
        amount_total=2999,
        automatic_tax={"enabled": False},
        created=1,
        currency="usd",
        custom_fields=[],
        custom_text={},
        customer=stripe_customer_id,
        expires_at=2,
        line_items={
            "object": "list",
            "data": [
                {
                    "id": "li_checkout_1",
                    "object": "item",
                    "amount_discount": 0,
                    "amount_subtotal": 2999,
                    "amount_tax": 0,
                    "amount_total": 2999,
                    "currency": "usd",
                    "price": price.model_dump(mode="json"),
                    "quantity": 1,
                }
            ],
            "has_more": False,
            "url": "/v1/checkout/sessions/cs_test/line_items",
        },
        livemode=False,
        mode="payment",
        payment_intent="pi_test",
        payment_method_types=["card"],
        payment_status="paid",
        shipping_options=[],
    )
    subscription = SubscriptionModel(
        object="subscription",
        id="sub_test",
        automatic_tax={"enabled": False},
        billing_cycle_anchor=1,
        billing_mode={"type": "flexible"},
        cancel_at_period_end=False,
        collection_method="charge_automatically",
        created=1,
        currency="usd",
        customer=stripe_customer_id,
        discounts=[],
        invoice_settings={"issuer": {"type": "self"}},
        items={
            "object": "list",
            "data": [],
            "has_more": False,
            "url": "/v1/subscription_items?subscription=sub_test",
        },
        livemode=False,
        metadata={},
        start_date=1,
        status="active",
    )
    now = datetime.now(timezone.utc)

    await db_connection.insert(
        [
            models.ProductPrice(
                product_id=models.ProductID.SUBSCRIPTION_GOLD,
                price_id=models.PriceID.DEFAULT,
                frequency=models.PriceBillingInterval.MONTH,
                stripe_price_id="price_test",
            ),
            models.StripeObject(
                stripe_id="cs_test",
                object_type="checkout.session",
                livemode=False,
                api_version="2026-03-25.dahlia",
                checkout_session=checkout_session.model_dump(mode="json"),
                stripe_customer_id=stripe_customer_id,
                internal_user_id=user.id,
                sync_status=SyncStatus.CLEAN,
                last_reconciled_at=now,
                latest_event_created_at=now,
            ),
            models.StripeObject(
                stripe_id="sub_test",
                object_type="subscription",
                livemode=False,
                api_version="2026-03-25.dahlia",
                subscription=subscription.model_dump(mode="json"),
                stripe_customer_id=stripe_customer_id,
                internal_user_id=user.id,
                sync_status=SyncStatus.CLEAN,
                last_reconciled_at=now,
                latest_event_created_at=now,
            ),
        ]
    )

    expected_response = MaterializeSubscriptionsResponse(
        stripe_customer_id=stripe_customer_id,
        user_id=user.id,
        checkout_session_count=1,
        subscription_count=1,
        resource_access_count=1,
        payment_count=1,
    )

    workflow = MaterializeSubscriptions()
    response = await workflow.run(
        stripe_customer_id=stripe_customer_id,
        internal_user_id=user.id,
    )

    assert response == expected_response
    checkout_sessions = await db_connection.exec(select(models.CheckoutSession))
    subscriptions = await db_connection.exec(select(models.Subscription))
    resource_access = await db_connection.exec(select(models.ResourceAccess))
    payments = await db_connection.exec(select(models.Payment))
    projection_states = await db_connection.exec(select(models.BillingProjectionState))
    refreshed_users = await db_connection.exec(
        select(models.User).where(models.User.id == user.id)
    )

    assert len(checkout_sessions) == 1
    assert checkout_sessions[0].stripe_checkout_session_id == "cs_test"
    assert checkout_sessions[0].stripe_payment_intent_id == "pi_test"
    assert checkout_sessions[0].stripe_customer_id == stripe_customer_id

    assert len(subscriptions) == 1
    assert subscriptions[0].stripe_subscription_id == "sub_test"
    assert subscriptions[0].stripe_status == StripeStatus.ACTIVE

    assert len(resource_access) == 1
    assert resource_access[0].is_perpetual is True
    assert resource_access[0].stripe_price_id == "price_test"
    assert resource_access[0].product_id == models.ProductID.SUBSCRIPTION_GOLD

    assert len(payments) == 1
    assert payments[0].paid_amount == 2999
    assert payments[0].stripe_customer_id == stripe_customer_id
    assert payments[0].stripe_price_id == "price_test"

    assert len(projection_states) == 1
    assert projection_states[0].projection_status == SyncStatus.CLEAN
    assert projection_states[0].stripe_customer_id == stripe_customer_id

    assert len(refreshed_users) == 1
    assert refreshed_users[0].stripe_customer_id == stripe_customer_id
