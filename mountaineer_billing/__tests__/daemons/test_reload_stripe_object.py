from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from typing import Annotated, Callable
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from mountaineer_billing.daemons import reload_stripe_object as reload_module
from mountaineer_billing.daemons.reload_stripe_object import (
    LoadSavedStripeEventResponse,
    ReloadStripeObject,
    ReloadStripeObjectPayload,
    ReloadStripeObjectResponse,
)
from mountaineer_billing.stripe.v2026_03_25_dahlia.models import (
    ChargeModel,
    CustomerModel,
    Event,
    InvoiceModel,
    PaymentIntent,
    PriceModel,
    ProductModel,
    SubscriptionModel,
)
from mountaineer_billing.stripe.v2026_03_25_dahlia.models.checkout import Session

API_VERSION = "2026-03-25.dahlia"
RELOAD_ACTION_NAMES = (
    "reload_charge",
    "reload_checkout_session",
    "reload_customer",
    "reload_invoice",
    "reload_payment_intent",
    "reload_price",
    "reload_product",
    "reload_subscription",
)

OBJECT_TYPE_TO_ACTION_NAME = {
    "charge": "reload_charge",
    "checkout.session": "reload_checkout_session",
    "customer": "reload_customer",
    "invoice": "reload_invoice",
    "payment_intent": "reload_payment_intent",
    "price": "reload_price",
    "product": "reload_product",
    "subscription": "reload_subscription",
}


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


for versioned_model in (
    ChargeModel,
    CustomerModel,
    Event,
    InvoiceModel,
    PaymentIntent,
    PriceModel,
    ProductModel,
    Session,
    SubscriptionModel,
):
    rebuild_versioned_model(versioned_model)


def build_charge_payload() -> tuple[ChargeModel, str | None]:
    customer_id = "cus_charge"
    return (
        ChargeModel(
            object="charge",
            id="ch_test",
            created=1,
            livemode=False,
            amount=100,
            amount_captured=100,
            amount_refunded=0,
            billing_details={},
            captured=True,
            currency="usd",
            customer=customer_id,
            disputed=False,
            metadata={},
            paid=True,
            refunded=False,
            status="succeeded",
        ),
        customer_id,
    )


def build_checkout_session_payload() -> tuple[Session, str | None]:
    customer_id = "cus_checkout"
    return (
        Session(
            object="checkout.session",
            id="cs_test",
            automatic_tax={"enabled": False},
            created=1,
            custom_fields=[],
            custom_text={},
            customer=customer_id,
            expires_at=2,
            livemode=False,
            mode="payment",
            payment_method_types=["card"],
            payment_status="paid",
            shipping_options=[],
        ),
        customer_id,
    )


def build_customer_payload() -> tuple[CustomerModel, str | None]:
    customer_id = "cus_test"
    return (
        CustomerModel(
            object="customer",
            id=customer_id,
            created=1,
            livemode=False,
        ),
        customer_id,
    )


def build_invoice_payload() -> tuple[InvoiceModel, str | None]:
    customer_id = "cus_invoice"
    return (
        InvoiceModel(
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
            customer=customer_id,
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
        ),
        customer_id,
    )


def build_payment_intent_payload() -> tuple[PaymentIntent, str | None]:
    customer_id = "cus_payment_intent"
    return (
        PaymentIntent(
            object="payment_intent",
            id="pi_test",
            created=1,
            customer=customer_id,
            livemode=False,
            status="succeeded",
        ),
        customer_id,
    )


def build_price_payload() -> tuple[PriceModel, str | None]:
    return (
        PriceModel(
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
        ),
        None,
    )


def build_product_payload() -> tuple[ProductModel, str | None]:
    return (
        ProductModel(
            object="product",
            id="prod_test",
            active=True,
            created=1,
            images=[],
            livemode=False,
            marketing_features=[],
            metadata={},
            name="Test Product",
            updated=2,
        ),
        None,
    )


def build_subscription_payload() -> tuple[SubscriptionModel, str | None]:
    customer_id = "cus_subscription"
    return (
        SubscriptionModel(
            object="subscription",
            id="sub_test",
            automatic_tax={"enabled": False},
            billing_cycle_anchor=1,
            billing_mode={"type": "flexible"},
            cancel_at_period_end=False,
            collection_method="charge_automatically",
            created=1,
            currency="usd",
            customer=customer_id,
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
        ),
        customer_id,
    )


def build_event_model(
    *,
    event_id: str,
    event_type: str,
    object_model: BaseModel,
) -> Event:
    return Event(
        id=event_id,
        object="event",
        api_version=API_VERSION,
        created=1,
        data={
            "object": object_model.model_dump(mode="json"),
        },
        livemode=False,
        pending_webhooks=0,
        type=event_type,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event_type", "object_type", "typed_field", "payload_builder"),
    [
        ("charge.succeeded", "charge", "charge", build_charge_payload),
        (
            "checkout.session.completed",
            "checkout.session",
            "checkout_session",
            build_checkout_session_payload,
        ),
        ("customer.updated", "customer", "customer", build_customer_payload),
        ("invoice.paid", "invoice", "invoice", build_invoice_payload),
        (
            "payment_intent.succeeded",
            "payment_intent",
            "payment_intent",
            build_payment_intent_payload,
        ),
        ("price.updated", "price", "price", build_price_payload),
        ("product.updated", "product", "product", build_product_payload),
        (
            "customer.subscription.updated",
            "subscription",
            "subscription",
            build_subscription_payload,
        ),
    ],
)
async def test_reload_stripe_object_workflow_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    event_type: str,
    object_type: str,
    typed_field: str,
    payload_builder: Callable[[], tuple[BaseModel, str | None]],
) -> None:
    object_model, expected_customer_id = payload_builder()
    event_id = uuid4()
    event_model = build_event_model(
        event_id=f"evt_{object_type.replace('.', '_')}",
        event_type=event_type,
        object_model=object_model,
    )
    hydrated_event = LoadSavedStripeEventResponse(
        event_id=event_id,
        stripe_event_id=event_model.id,
        livemode=False,
        latest_event_created_at=datetime.now(timezone.utc),
        payload=ReloadStripeObjectPayload(
            event=event_model,
            **{typed_field: object_model},
        ),
    )
    expected_response = ReloadStripeObjectResponse(
        event_id=event_id,
        stripe_event_id=event_model.id,
        stripe_object_id=object_model.model_dump(mode="json")["id"],
        object_type=object_type,
        stripe_customer_id=expected_customer_id,
    )

    load_saved_stripe_event = AsyncMock(return_value=hydrated_event)
    monkeypatch.setattr(
        reload_module,
        "load_saved_stripe_event",
        load_saved_stripe_event,
    )

    action_mocks: dict[str, AsyncMock] = {}
    expected_action_name = OBJECT_TYPE_TO_ACTION_NAME[object_type]
    for action_name in RELOAD_ACTION_NAMES:
        action_mock = AsyncMock(
            return_value=expected_response
            if action_name == expected_action_name
            else None
        )
        monkeypatch.setattr(reload_module, action_name, action_mock)
        action_mocks[action_name] = action_mock

    workflow = ReloadStripeObject()
    response = await ReloadStripeObject.__workflow_run_impl__(
        workflow, event_id=event_id
    )

    assert response == expected_response
    load_saved_stripe_event.assert_awaited_once()
    load_request = load_saved_stripe_event.await_args.args[0]
    assert load_request.event_id == event_id

    for action_name, action_mock in action_mocks.items():
        if action_name == expected_action_name:
            action_mock.assert_awaited_once_with(hydrated_event)
        else:
            action_mock.assert_not_awaited()
