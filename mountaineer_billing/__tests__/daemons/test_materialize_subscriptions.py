from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from typing import Annotated
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from mountaineer_billing.daemons import (
    materialize_subscriptions as materialize_module,
)
from mountaineer_billing.daemons.materialize_subscriptions import (
    CheckoutSessionMaterializedRecord,
    LoadMaterializationContextResponse,
    MaterializedSubscriptionState,
    MaterializeSubscriptions,
    MaterializeSubscriptionsRequest,
    MaterializeSubscriptionsResponse,
    PaymentMaterializedRecord,
    ProductPriceReference,
    ResourceAccessMaterializedRecord,
    SubscriptionMaterializedRecord,
)
from mountaineer_billing.enums import StripeStatus
from mountaineer_billing.stripe.v2026_03_25_dahlia.models import (
    InvoiceModel,
    SubscriptionModel,
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


for versioned_model in (InvoiceModel, Session, SubscriptionModel):
    rebuild_versioned_model(versioned_model)


@pytest.mark.asyncio
async def test_materialize_subscriptions_workflow_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stripe_customer_id = "cus_materialize"
    internal_user_id = uuid4()
    checkout_session = Session(
        object="checkout.session",
        id="cs_test",
        automatic_tax={"enabled": False},
        created=1,
        custom_fields=[],
        custom_text={},
        customer=stripe_customer_id,
        expires_at=2,
        livemode=False,
        mode="payment",
        payment_intent="pi_test",
        payment_method_types=["card"],
        payment_status="paid",
        shipping_options=[],
    )
    invoice = InvoiceModel(
        object="invoice",
        id="in_test",
        amount_due=100,
        amount_overpaid=0,
        amount_paid=100,
        amount_remaining=0,
        amount_shipping=0,
        attempt_count=1,
        attempted=True,
        auto_advance=False,
        automatic_tax={"enabled": False},
        collection_method="charge_automatically",
        created=1,
        currency="usd",
        customer=stripe_customer_id,
        default_tax_rates=[],
        discounts=[],
        issuer={"type": "self"},
        lines={
            "object": "list",
            "data": [],
            "has_more": False,
            "url": "/v1/invoices/in_test/lines",
        },
        livemode=False,
        payment_settings={"payment_method_options": {}},
        period_end=2,
        period_start=1,
        post_payment_credit_notes_amount=0,
        pre_payment_credit_notes_amount=0,
        starting_balance=0,
        status_transitions={},
        subtotal=100,
        total=100,
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

    loaded_context = LoadMaterializationContextResponse(
        stripe_customer_id=stripe_customer_id,
        internal_user_id=internal_user_id,
        user_id=internal_user_id,
        checkout_sessions=[checkout_session],
        invoices=[invoice],
        subscriptions=[subscription],
        product_prices=[
            ProductPriceReference(
                stripe_price_id="price_test",
                product_id="SUBSCRIPTION_GOLD",
            )
        ],
    )
    materialized_state = MaterializedSubscriptionState(
        stripe_customer_id=stripe_customer_id,
        user_id=internal_user_id,
        checkout_sessions=[
            CheckoutSessionMaterializedRecord(
                stripe_checkout_session_id="cs_test",
                stripe_payment_intent_id="pi_test",
                stripe_subscription_id="sub_test",
                stripe_customer_id=stripe_customer_id,
                user_id=internal_user_id,
            )
        ],
        subscriptions=[
            SubscriptionMaterializedRecord(
                stripe_subscription_id="sub_test",
                stripe_status=StripeStatus.ACTIVE,
                stripe_current_period_start=datetime.now(timezone.utc),
                stripe_current_period_end=datetime.now(timezone.utc),
                stripe_checkout_session_id="cs_test",
                user_id=internal_user_id,
            )
        ],
        resource_access=[
            ResourceAccessMaterializedRecord(
                started_datetime=datetime.now(timezone.utc),
                ended_datetime=None,
                stripe_subscription_id="sub_test",
                is_perpetual=False,
                prorated_usage=1.0,
                stripe_price_id="price_test",
                stripe_product_id="prod_test",
                product_id="SUBSCRIPTION_GOLD",
                user_id=internal_user_id,
            )
        ],
        payments=[
            PaymentMaterializedRecord(
                paid_amount=2999,
                total_price_amount=2999,
                price_ratio=1.0,
                stripe_subscription_id="sub_test",
                stripe_customer_id=stripe_customer_id,
                stripe_price_id="price_test",
                stripe_invoice_id="in_test",
                user_id=internal_user_id,
            )
        ],
    )
    expected_response = MaterializeSubscriptionsResponse(
        stripe_customer_id=stripe_customer_id,
        user_id=internal_user_id,
        checkout_session_count=1,
        subscription_count=1,
        resource_access_count=1,
        payment_count=1,
    )

    load_materialization_context = AsyncMock(return_value=loaded_context)
    build_materialized_subscription_state = AsyncMock(return_value=materialized_state)
    persist_materialized_subscription_state = AsyncMock(return_value=expected_response)

    monkeypatch.setattr(
        materialize_module,
        "load_materialization_context",
        load_materialization_context,
    )
    monkeypatch.setattr(
        materialize_module,
        "build_materialized_subscription_state",
        build_materialized_subscription_state,
    )
    monkeypatch.setattr(
        materialize_module,
        "persist_materialized_subscription_state",
        persist_materialized_subscription_state,
    )

    workflow = MaterializeSubscriptions()
    response = await workflow.run(
        stripe_customer_id=stripe_customer_id,
        internal_user_id=internal_user_id,
    )

    assert response == expected_response
    load_materialization_context.assert_awaited_once()
    load_request = load_materialization_context.await_args.args[0]
    assert load_request == MaterializeSubscriptionsRequest(
        stripe_customer_id=stripe_customer_id,
        internal_user_id=internal_user_id,
    )
    build_materialized_subscription_state.assert_awaited_once_with(loaded_context)
    persist_materialized_subscription_state.assert_awaited_once_with(materialized_state)
