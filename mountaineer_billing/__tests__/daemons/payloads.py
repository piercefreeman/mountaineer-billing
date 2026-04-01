from __future__ import annotations

from importlib import import_module
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel

from mountaineer_billing.stripe.v2026_03_25_dahlia.models import (
    CustomerModel,
    PriceModel,
    ProductModel,
)
from mountaineer_billing.stripe.v2026_03_25_dahlia.models.checkout import Session

API_VERSION = "2026-03-25.dahlia"


def rebuild_versioned_model(model_type: type[BaseModel]) -> type[BaseModel]:
    """Rebuild a generated Stripe model before daemon tests instantiate it.

    The generated versioned models rely on `_internal` symbols during Pydantic
    schema rebuilding. The shared daemon payload helpers call this at import
    time so the builders below can create valid test payloads.
    """

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


for versioned_model in (ProductModel, PriceModel, CustomerModel, Session):
    rebuild_versioned_model(versioned_model)


def build_product_payload(*, product_id: str, name: str) -> dict[str, object]:
    """Build a Stripe product payload for daemon tests that materialize products.

    This helper returns JSON-shaped data that matches the current generated
    Stripe model, so tests can seed webhook payloads or Stripe fetch responses
    without hand-writing large product dictionaries.
    """

    return ProductModel(
        object="product",
        id=product_id,
        active=True,
        created=1,
        images=[],
        livemode=False,
        marketing_features=[],
        metadata={},
        name=name,
        updated=2,
    ).model_dump(mode="json")


def build_price_payload(
    *,
    price_id: str,
    product: dict[str, object],
    unit_amount: int,
    recurring_interval: str,
) -> dict[str, object]:
    """Build a Stripe price payload linked to a test product payload.

    Daemon tests use this when they need a recurring price object that can be
    stored or reloaded alongside a product during webhook processing.
    """

    return PriceModel(
        object="price",
        id=price_id,
        active=True,
        billing_scheme="per_unit",
        created=1,
        currency="usd",
        livemode=False,
        metadata={},
        product=product,
        recurring={
            "interval": recurring_interval,
            "interval_count": 1,
            "usage_type": "licensed",
        },
        type="recurring",
        unit_amount=unit_amount,
    ).model_dump(mode="json")


def build_customer_payload(
    *,
    customer_id: str,
    user_id: UUID,
) -> dict[str, object]:
    """Build a Stripe customer payload associated with a billing test user.

    The helper encodes the internal user id into Stripe metadata, mirroring the
    shape expected by daemon flows that project customer state back onto local
    billing models.
    """

    return CustomerModel(
        object="customer",
        id=customer_id,
        created=1,
        livemode=False,
        email=f"{user_id}@example.com",
        metadata={"internal_user_id": str(user_id)},
        name="Type Benchmark User",
    ).model_dump(mode="json")


def build_checkout_session_payload(
    *,
    session_id: str,
    customer: dict[str, object],
    price: dict[str, object],
    client_reference_id: str,
    mode: str,
    payment_intent_id: str,
    subscription_id: str,
    invoice_id: str,
) -> dict[str, object]:
    """Build a paid checkout session payload for daemon and projection tests.

    This is used when tests need a realistic `checkout.session` object that
    ties together the customer, price, invoice, payment intent, and
    subscription references processed by Stripe reload/materialization flows.
    """

    return Session(
        object="checkout.session",
        id=session_id,
        amount_subtotal=price.get("unit_amount"),
        amount_total=price.get("unit_amount"),
        automatic_tax={"enabled": False},
        client_reference_id=client_reference_id,
        created=1,
        currency=str(price.get("currency", "usd")),
        custom_fields=[],
        custom_text={},
        customer=customer,
        customer_email=str(customer.get("email")),
        expires_at=2,
        invoice=invoice_id,
        livemode=False,
        mode=mode,
        payment_intent=payment_intent_id,
        payment_method_types=["card"],
        payment_status="paid",
        shipping_options=[],
        subscription=subscription_id,
    ).model_dump(mode="json")
