# ruff: noqa: I001
from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAlias

from ..type_helpers import LazyAdapter, make_lazy_payload_type

VERSION_DISCRIMINATOR_FIELD = "mountaineer_billing_api_version"

_MODEL_REGISTRY: dict[str, dict[str, tuple[str, str]]] = {
    "event": {
        "2023-08-16": (".v2023_08_16.models", "Event"),
        "2024-04-03": (".v2024_04_03.models", "Event"),
        "2023-10-16": (".v2023_10_16.models", "Event"),
        "2024-04-10": (".v2024_04_10.models", "Event"),
        "2024-06-20": (".v2024_06_20.models", "Event"),
        "2024-09-30.acacia": (".v2024_09_30_acacia.models", "Event"),
        "2024-10-28.acacia": (".v2024_10_28_acacia.models", "Event"),
        "2024-11-20.acacia": (".v2024_11_20_acacia.models", "Event"),
        "2024-12-18.acacia": (".v2024_12_18_acacia.models", "Event"),
        "2025-01-27.acacia": (".v2025_01_27_acacia.models", "Event"),
        "2025-02-24.acacia": (".v2025_02_24_acacia.models", "Event"),
        "2025-03-31.basil": (".v2025_03_31_basil.models", "Event"),
        "2025-04-30.basil": (".v2025_04_30_basil.models", "Event"),
        "2025-05-28.basil": (".v2025_05_28_basil.models", "Event"),
        "2025-06-30.basil": (".v2025_06_30_basil.models", "Event"),
        "2025-07-30.basil": (".v2025_07_30_basil.models", "Event"),
        "2025-08-27.basil": (".v2025_08_27_basil.models", "Event"),
        "2025-09-30.clover": (".v2025_09_30_clover.models", "Event"),
        "2025-10-29.clover": (".v2025_10_29_clover.models", "Event"),
        "2025-11-17.clover": (".v2025_11_17_clover.models", "Event"),
        "2025-12-15.clover": (".v2025_12_15_clover.models", "Event"),
        "2026-01-28.clover": (".v2026_01_28_clover.models", "Event"),
        "2026-02-25.clover": (".v2026_02_25_clover.models", "Event"),
        "2026-03-25.dahlia": (".v2026_03_25_dahlia.models", "Event"),
    },
    "charge": {
        "2023-08-16": (".v2023_08_16.models", "ChargeModel"),
        "2024-04-03": (".v2024_04_03.models", "ChargeModel"),
        "2023-10-16": (".v2023_10_16.models", "ChargeModel"),
        "2024-04-10": (".v2024_04_10.models", "ChargeModel"),
        "2024-06-20": (".v2024_06_20.models", "ChargeModel"),
        "2024-09-30.acacia": (".v2024_09_30_acacia.models", "ChargeModel"),
        "2024-10-28.acacia": (".v2024_10_28_acacia.models", "ChargeModel"),
        "2024-11-20.acacia": (".v2024_11_20_acacia.models", "ChargeModel"),
        "2024-12-18.acacia": (".v2024_12_18_acacia.models", "ChargeModel"),
        "2025-01-27.acacia": (".v2025_01_27_acacia.models", "ChargeModel"),
        "2025-02-24.acacia": (".v2025_02_24_acacia.models", "ChargeModel"),
        "2025-03-31.basil": (".v2025_03_31_basil.models", "ChargeModel"),
        "2025-04-30.basil": (".v2025_04_30_basil.models", "ChargeModel"),
        "2025-05-28.basil": (".v2025_05_28_basil.models", "ChargeModel"),
        "2025-06-30.basil": (".v2025_06_30_basil.models", "ChargeModel"),
        "2025-07-30.basil": (".v2025_07_30_basil.models", "ChargeModel"),
        "2025-08-27.basil": (".v2025_08_27_basil.models", "ChargeModel"),
        "2025-09-30.clover": (".v2025_09_30_clover.models", "ChargeModel"),
        "2025-10-29.clover": (".v2025_10_29_clover.models", "ChargeModel"),
        "2025-11-17.clover": (".v2025_11_17_clover.models", "ChargeModel"),
        "2025-12-15.clover": (".v2025_12_15_clover.models", "ChargeModel"),
        "2026-01-28.clover": (".v2026_01_28_clover.models", "ChargeModel"),
        "2026-02-25.clover": (".v2026_02_25_clover.models", "ChargeModel"),
        "2026-03-25.dahlia": (".v2026_03_25_dahlia.models", "ChargeModel"),
    },
    "checkout.session": {
        "2023-08-16": (".v2023_08_16.models.checkout", "Session"),
        "2024-04-03": (".v2024_04_03.models.checkout", "Session"),
        "2023-10-16": (".v2023_10_16.models.checkout", "Session"),
        "2024-04-10": (".v2024_04_10.models.checkout", "Session"),
        "2024-06-20": (".v2024_06_20.models.checkout", "Session"),
        "2024-09-30.acacia": (".v2024_09_30_acacia.models.checkout", "Session"),
        "2024-10-28.acacia": (".v2024_10_28_acacia.models.checkout", "Session"),
        "2024-11-20.acacia": (".v2024_11_20_acacia.models.checkout", "Session"),
        "2024-12-18.acacia": (".v2024_12_18_acacia.models.checkout", "Session"),
        "2025-01-27.acacia": (".v2025_01_27_acacia.models.checkout", "Session"),
        "2025-02-24.acacia": (".v2025_02_24_acacia.models.checkout", "Session"),
        "2025-03-31.basil": (".v2025_03_31_basil.models.checkout", "Session"),
        "2025-04-30.basil": (".v2025_04_30_basil.models.checkout", "Session"),
        "2025-05-28.basil": (".v2025_05_28_basil.models.checkout", "Session"),
        "2025-06-30.basil": (".v2025_06_30_basil.models.checkout", "Session"),
        "2025-07-30.basil": (".v2025_07_30_basil.models.checkout", "Session"),
        "2025-08-27.basil": (".v2025_08_27_basil.models.checkout", "Session"),
        "2025-09-30.clover": (".v2025_09_30_clover.models.checkout", "Session"),
        "2025-10-29.clover": (".v2025_10_29_clover.models.checkout", "Session"),
        "2025-11-17.clover": (".v2025_11_17_clover.models.checkout", "Session"),
        "2025-12-15.clover": (".v2025_12_15_clover.models.checkout", "Session"),
        "2026-01-28.clover": (".v2026_01_28_clover.models.checkout", "Session"),
        "2026-02-25.clover": (".v2026_02_25_clover.models.checkout", "Session"),
        "2026-03-25.dahlia": (".v2026_03_25_dahlia.models.checkout", "Session"),
    },
    "customer": {
        "2023-08-16": (".v2023_08_16.models", "CustomerModel"),
        "2024-04-03": (".v2024_04_03.models", "CustomerModel"),
        "2023-10-16": (".v2023_10_16.models", "CustomerModel"),
        "2024-04-10": (".v2024_04_10.models", "CustomerModel"),
        "2024-06-20": (".v2024_06_20.models", "CustomerModel"),
        "2024-09-30.acacia": (".v2024_09_30_acacia.models", "CustomerModel"),
        "2024-10-28.acacia": (".v2024_10_28_acacia.models", "CustomerModel"),
        "2024-11-20.acacia": (".v2024_11_20_acacia.models", "CustomerModel"),
        "2024-12-18.acacia": (".v2024_12_18_acacia.models", "CustomerModel"),
        "2025-01-27.acacia": (".v2025_01_27_acacia.models", "CustomerModel"),
        "2025-02-24.acacia": (".v2025_02_24_acacia.models", "CustomerModel"),
        "2025-03-31.basil": (".v2025_03_31_basil.models", "CustomerModel"),
        "2025-04-30.basil": (".v2025_04_30_basil.models", "CustomerModel"),
        "2025-05-28.basil": (".v2025_05_28_basil.models", "CustomerModel"),
        "2025-06-30.basil": (".v2025_06_30_basil.models", "CustomerModel"),
        "2025-07-30.basil": (".v2025_07_30_basil.models", "CustomerModel"),
        "2025-08-27.basil": (".v2025_08_27_basil.models", "CustomerModel"),
        "2025-09-30.clover": (".v2025_09_30_clover.models", "CustomerModel"),
        "2025-10-29.clover": (".v2025_10_29_clover.models", "CustomerModel"),
        "2025-11-17.clover": (".v2025_11_17_clover.models", "CustomerModel"),
        "2025-12-15.clover": (".v2025_12_15_clover.models", "CustomerModel"),
        "2026-01-28.clover": (".v2026_01_28_clover.models", "CustomerModel"),
        "2026-02-25.clover": (".v2026_02_25_clover.models", "CustomerModel"),
        "2026-03-25.dahlia": (".v2026_03_25_dahlia.models", "CustomerModel"),
    },
    "invoice": {
        "2023-08-16": (".v2023_08_16.models", "InvoiceModel"),
        "2024-04-03": (".v2024_04_03.models", "InvoiceModel"),
        "2023-10-16": (".v2023_10_16.models", "InvoiceModel"),
        "2024-04-10": (".v2024_04_10.models", "InvoiceModel"),
        "2024-06-20": (".v2024_06_20.models", "InvoiceModel"),
        "2024-09-30.acacia": (".v2024_09_30_acacia.models", "InvoiceModel"),
        "2024-10-28.acacia": (".v2024_10_28_acacia.models", "InvoiceModel"),
        "2024-11-20.acacia": (".v2024_11_20_acacia.models", "InvoiceModel"),
        "2024-12-18.acacia": (".v2024_12_18_acacia.models", "InvoiceModel"),
        "2025-01-27.acacia": (".v2025_01_27_acacia.models", "InvoiceModel"),
        "2025-02-24.acacia": (".v2025_02_24_acacia.models", "InvoiceModel"),
        "2025-03-31.basil": (".v2025_03_31_basil.models", "InvoiceModel"),
        "2025-04-30.basil": (".v2025_04_30_basil.models", "InvoiceModel"),
        "2025-05-28.basil": (".v2025_05_28_basil.models", "InvoiceModel"),
        "2025-06-30.basil": (".v2025_06_30_basil.models", "InvoiceModel"),
        "2025-07-30.basil": (".v2025_07_30_basil.models", "InvoiceModel"),
        "2025-08-27.basil": (".v2025_08_27_basil.models", "InvoiceModel"),
        "2025-09-30.clover": (".v2025_09_30_clover.models", "InvoiceModel"),
        "2025-10-29.clover": (".v2025_10_29_clover.models", "InvoiceModel"),
        "2025-11-17.clover": (".v2025_11_17_clover.models", "InvoiceModel"),
        "2025-12-15.clover": (".v2025_12_15_clover.models", "InvoiceModel"),
        "2026-01-28.clover": (".v2026_01_28_clover.models", "InvoiceModel"),
        "2026-02-25.clover": (".v2026_02_25_clover.models", "InvoiceModel"),
        "2026-03-25.dahlia": (".v2026_03_25_dahlia.models", "InvoiceModel"),
    },
    "payment_intent": {
        "2023-08-16": (".v2023_08_16.models", "PaymentIntent"),
        "2024-04-03": (".v2024_04_03.models", "PaymentIntent"),
        "2023-10-16": (".v2023_10_16.models", "PaymentIntent"),
        "2024-04-10": (".v2024_04_10.models", "PaymentIntent"),
        "2024-06-20": (".v2024_06_20.models", "PaymentIntent"),
        "2024-09-30.acacia": (".v2024_09_30_acacia.models", "PaymentIntent"),
        "2024-10-28.acacia": (".v2024_10_28_acacia.models", "PaymentIntent"),
        "2024-11-20.acacia": (".v2024_11_20_acacia.models", "PaymentIntent"),
        "2024-12-18.acacia": (".v2024_12_18_acacia.models", "PaymentIntent"),
        "2025-01-27.acacia": (".v2025_01_27_acacia.models", "PaymentIntent"),
        "2025-02-24.acacia": (".v2025_02_24_acacia.models", "PaymentIntent"),
        "2025-03-31.basil": (".v2025_03_31_basil.models", "PaymentIntent"),
        "2025-04-30.basil": (".v2025_04_30_basil.models", "PaymentIntent"),
        "2025-05-28.basil": (".v2025_05_28_basil.models", "PaymentIntent"),
        "2025-06-30.basil": (".v2025_06_30_basil.models", "PaymentIntent"),
        "2025-07-30.basil": (".v2025_07_30_basil.models", "PaymentIntent"),
        "2025-08-27.basil": (".v2025_08_27_basil.models", "PaymentIntent"),
        "2025-09-30.clover": (".v2025_09_30_clover.models", "PaymentIntent"),
        "2025-10-29.clover": (".v2025_10_29_clover.models", "PaymentIntent"),
        "2025-11-17.clover": (".v2025_11_17_clover.models", "PaymentIntent"),
        "2025-12-15.clover": (".v2025_12_15_clover.models", "PaymentIntent"),
        "2026-01-28.clover": (".v2026_01_28_clover.models", "PaymentIntent"),
        "2026-02-25.clover": (".v2026_02_25_clover.models", "PaymentIntent"),
        "2026-03-25.dahlia": (".v2026_03_25_dahlia.models", "PaymentIntent"),
    },
    "price": {
        "2023-08-16": (".v2023_08_16.models", "Price"),
        "2024-04-03": (".v2024_04_03.models", "Price"),
        "2023-10-16": (".v2023_10_16.models", "Price"),
        "2024-04-10": (".v2024_04_10.models", "Price"),
        "2024-06-20": (".v2024_06_20.models", "Price"),
        "2024-09-30.acacia": (".v2024_09_30_acacia.models", "Price"),
        "2024-10-28.acacia": (".v2024_10_28_acacia.models", "Price"),
        "2024-11-20.acacia": (".v2024_11_20_acacia.models", "Price"),
        "2024-12-18.acacia": (".v2024_12_18_acacia.models", "Price"),
        "2025-01-27.acacia": (".v2025_01_27_acacia.models", "Price"),
        "2025-02-24.acacia": (".v2025_02_24_acacia.models", "Price"),
        "2025-03-31.basil": (".v2025_03_31_basil.models", "Price"),
        "2025-04-30.basil": (".v2025_04_30_basil.models", "Price"),
        "2025-05-28.basil": (".v2025_05_28_basil.models", "Price"),
        "2025-06-30.basil": (".v2025_06_30_basil.models", "Price"),
        "2025-07-30.basil": (".v2025_07_30_basil.models", "Price"),
        "2025-08-27.basil": (".v2025_08_27_basil.models", "Price"),
        "2025-09-30.clover": (".v2025_09_30_clover.models", "Price"),
        "2025-10-29.clover": (".v2025_10_29_clover.models", "Price"),
        "2025-11-17.clover": (".v2025_11_17_clover.models", "Price"),
        "2025-12-15.clover": (".v2025_12_15_clover.models", "PriceModel"),
        "2026-01-28.clover": (".v2026_01_28_clover.models", "PriceModel"),
        "2026-02-25.clover": (".v2026_02_25_clover.models", "PriceModel"),
        "2026-03-25.dahlia": (".v2026_03_25_dahlia.models", "PriceModel"),
    },
    "product": {
        "2023-08-16": (".v2023_08_16.models", "ProductModel"),
        "2024-04-03": (".v2024_04_03.models", "ProductModel"),
        "2023-10-16": (".v2023_10_16.models", "ProductModel"),
        "2024-04-10": (".v2024_04_10.models", "ProductModel"),
        "2024-06-20": (".v2024_06_20.models", "ProductModel"),
        "2024-09-30.acacia": (".v2024_09_30_acacia.models", "ProductModel"),
        "2024-10-28.acacia": (".v2024_10_28_acacia.models", "ProductModel"),
        "2024-11-20.acacia": (".v2024_11_20_acacia.models", "ProductModel"),
        "2024-12-18.acacia": (".v2024_12_18_acacia.models", "ProductModel"),
        "2025-01-27.acacia": (".v2025_01_27_acacia.models", "ProductModel"),
        "2025-02-24.acacia": (".v2025_02_24_acacia.models", "ProductModel"),
        "2025-03-31.basil": (".v2025_03_31_basil.models", "ProductModel"),
        "2025-04-30.basil": (".v2025_04_30_basil.models", "ProductModel"),
        "2025-05-28.basil": (".v2025_05_28_basil.models", "ProductModel"),
        "2025-06-30.basil": (".v2025_06_30_basil.models", "ProductModel"),
        "2025-07-30.basil": (".v2025_07_30_basil.models", "ProductModel"),
        "2025-08-27.basil": (".v2025_08_27_basil.models", "ProductModel"),
        "2025-09-30.clover": (".v2025_09_30_clover.models", "ProductModel"),
        "2025-10-29.clover": (".v2025_10_29_clover.models", "ProductModel"),
        "2025-11-17.clover": (".v2025_11_17_clover.models", "ProductModel"),
        "2025-12-15.clover": (".v2025_12_15_clover.models", "ProductModel"),
        "2026-01-28.clover": (".v2026_01_28_clover.models", "ProductModel"),
        "2026-02-25.clover": (".v2026_02_25_clover.models", "ProductModel"),
        "2026-03-25.dahlia": (".v2026_03_25_dahlia.models", "ProductModel"),
    },
    "subscription": {
        "2023-08-16": (".v2023_08_16.models", "Subscription"),
        "2024-04-03": (".v2024_04_03.models", "Subscription"),
        "2023-10-16": (".v2023_10_16.models", "Subscription"),
        "2024-04-10": (".v2024_04_10.models", "Subscription"),
        "2024-06-20": (".v2024_06_20.models", "Subscription"),
        "2024-09-30.acacia": (".v2024_09_30_acacia.models", "Subscription"),
        "2024-10-28.acacia": (".v2024_10_28_acacia.models", "Subscription"),
        "2024-11-20.acacia": (".v2024_11_20_acacia.models", "Subscription"),
        "2024-12-18.acacia": (".v2024_12_18_acacia.models", "Subscription"),
        "2025-01-27.acacia": (".v2025_01_27_acacia.models", "Subscription"),
        "2025-02-24.acacia": (".v2025_02_24_acacia.models", "Subscription"),
        "2025-03-31.basil": (".v2025_03_31_basil.models", "SubscriptionModel"),
        "2025-04-30.basil": (".v2025_04_30_basil.models", "SubscriptionModel"),
        "2025-05-28.basil": (".v2025_05_28_basil.models", "SubscriptionModel"),
        "2025-06-30.basil": (".v2025_06_30_basil.models", "SubscriptionModel"),
        "2025-07-30.basil": (".v2025_07_30_basil.models", "SubscriptionModel"),
        "2025-08-27.basil": (".v2025_08_27_basil.models", "SubscriptionModel"),
        "2025-09-30.clover": (".v2025_09_30_clover.models", "SubscriptionModel"),
        "2025-10-29.clover": (".v2025_10_29_clover.models", "SubscriptionModel"),
        "2025-11-17.clover": (".v2025_11_17_clover.models", "SubscriptionModel"),
        "2025-12-15.clover": (".v2025_12_15_clover.models", "SubscriptionModel"),
        "2026-01-28.clover": (".v2026_01_28_clover.models", "SubscriptionModel"),
        "2026-02-25.clover": (".v2026_02_25_clover.models", "SubscriptionModel"),
        "2026-03-25.dahlia": (".v2026_03_25_dahlia.models", "SubscriptionModel"),
    },
}


LazyStripeAdapter = LazyAdapter

if TYPE_CHECKING:
    from .v2023_08_16.models import ChargeModel as v2023_08_16_charge
    from .v2023_08_16.models import CustomerModel as v2023_08_16_customer
    from .v2023_08_16.models import Event as v2023_08_16_event
    from .v2023_08_16.models import InvoiceModel as v2023_08_16_invoice
    from .v2023_08_16.models import PaymentIntent as v2023_08_16_payment_intent
    from .v2023_08_16.models import Price as v2023_08_16_price
    from .v2023_08_16.models import ProductModel as v2023_08_16_product
    from .v2023_08_16.models import Subscription as v2023_08_16_subscription
    from .v2023_08_16.models.checkout import Session as v2023_08_16_checkout_session
    from .v2023_10_16.models import ChargeModel as v2023_10_16_charge
    from .v2023_10_16.models import CustomerModel as v2023_10_16_customer
    from .v2023_10_16.models import Event as v2023_10_16_event
    from .v2023_10_16.models import InvoiceModel as v2023_10_16_invoice
    from .v2023_10_16.models import PaymentIntent as v2023_10_16_payment_intent
    from .v2023_10_16.models import Price as v2023_10_16_price
    from .v2023_10_16.models import ProductModel as v2023_10_16_product
    from .v2023_10_16.models import Subscription as v2023_10_16_subscription
    from .v2023_10_16.models.checkout import Session as v2023_10_16_checkout_session
    from .v2024_04_03.models import ChargeModel as v2024_04_03_charge
    from .v2024_04_03.models import CustomerModel as v2024_04_03_customer
    from .v2024_04_03.models import Event as v2024_04_03_event
    from .v2024_04_03.models import InvoiceModel as v2024_04_03_invoice
    from .v2024_04_03.models import PaymentIntent as v2024_04_03_payment_intent
    from .v2024_04_03.models import Price as v2024_04_03_price
    from .v2024_04_03.models import ProductModel as v2024_04_03_product
    from .v2024_04_03.models import Subscription as v2024_04_03_subscription
    from .v2024_04_03.models.checkout import Session as v2024_04_03_checkout_session
    from .v2024_04_10.models import ChargeModel as v2024_04_10_charge
    from .v2024_04_10.models import CustomerModel as v2024_04_10_customer
    from .v2024_04_10.models import Event as v2024_04_10_event
    from .v2024_04_10.models import InvoiceModel as v2024_04_10_invoice
    from .v2024_04_10.models import PaymentIntent as v2024_04_10_payment_intent
    from .v2024_04_10.models import Price as v2024_04_10_price
    from .v2024_04_10.models import ProductModel as v2024_04_10_product
    from .v2024_04_10.models import Subscription as v2024_04_10_subscription
    from .v2024_04_10.models.checkout import Session as v2024_04_10_checkout_session
    from .v2024_06_20.models import ChargeModel as v2024_06_20_charge
    from .v2024_06_20.models import CustomerModel as v2024_06_20_customer
    from .v2024_06_20.models import Event as v2024_06_20_event
    from .v2024_06_20.models import InvoiceModel as v2024_06_20_invoice
    from .v2024_06_20.models import PaymentIntent as v2024_06_20_payment_intent
    from .v2024_06_20.models import Price as v2024_06_20_price
    from .v2024_06_20.models import ProductModel as v2024_06_20_product
    from .v2024_06_20.models import Subscription as v2024_06_20_subscription
    from .v2024_06_20.models.checkout import Session as v2024_06_20_checkout_session
    from .v2024_09_30_acacia.models import ChargeModel as v2024_09_30_acacia_charge
    from .v2024_09_30_acacia.models import CustomerModel as v2024_09_30_acacia_customer
    from .v2024_09_30_acacia.models import Event as v2024_09_30_acacia_event
    from .v2024_09_30_acacia.models import InvoiceModel as v2024_09_30_acacia_invoice
    from .v2024_09_30_acacia.models import (
        PaymentIntent as v2024_09_30_acacia_payment_intent,
    )
    from .v2024_09_30_acacia.models import Price as v2024_09_30_acacia_price
    from .v2024_09_30_acacia.models import ProductModel as v2024_09_30_acacia_product
    from .v2024_09_30_acacia.models import (
        Subscription as v2024_09_30_acacia_subscription,
    )
    from .v2024_09_30_acacia.models.checkout import (
        Session as v2024_09_30_acacia_checkout_session,
    )
    from .v2024_10_28_acacia.models import ChargeModel as v2024_10_28_acacia_charge
    from .v2024_10_28_acacia.models import CustomerModel as v2024_10_28_acacia_customer
    from .v2024_10_28_acacia.models import Event as v2024_10_28_acacia_event
    from .v2024_10_28_acacia.models import InvoiceModel as v2024_10_28_acacia_invoice
    from .v2024_10_28_acacia.models import (
        PaymentIntent as v2024_10_28_acacia_payment_intent,
    )
    from .v2024_10_28_acacia.models import Price as v2024_10_28_acacia_price
    from .v2024_10_28_acacia.models import ProductModel as v2024_10_28_acacia_product
    from .v2024_10_28_acacia.models import (
        Subscription as v2024_10_28_acacia_subscription,
    )
    from .v2024_10_28_acacia.models.checkout import (
        Session as v2024_10_28_acacia_checkout_session,
    )
    from .v2024_11_20_acacia.models import ChargeModel as v2024_11_20_acacia_charge
    from .v2024_11_20_acacia.models import CustomerModel as v2024_11_20_acacia_customer
    from .v2024_11_20_acacia.models import Event as v2024_11_20_acacia_event
    from .v2024_11_20_acacia.models import InvoiceModel as v2024_11_20_acacia_invoice
    from .v2024_11_20_acacia.models import (
        PaymentIntent as v2024_11_20_acacia_payment_intent,
    )
    from .v2024_11_20_acacia.models import Price as v2024_11_20_acacia_price
    from .v2024_11_20_acacia.models import ProductModel as v2024_11_20_acacia_product
    from .v2024_11_20_acacia.models import (
        Subscription as v2024_11_20_acacia_subscription,
    )
    from .v2024_11_20_acacia.models.checkout import (
        Session as v2024_11_20_acacia_checkout_session,
    )
    from .v2024_12_18_acacia.models import ChargeModel as v2024_12_18_acacia_charge
    from .v2024_12_18_acacia.models import CustomerModel as v2024_12_18_acacia_customer
    from .v2024_12_18_acacia.models import Event as v2024_12_18_acacia_event
    from .v2024_12_18_acacia.models import InvoiceModel as v2024_12_18_acacia_invoice
    from .v2024_12_18_acacia.models import (
        PaymentIntent as v2024_12_18_acacia_payment_intent,
    )
    from .v2024_12_18_acacia.models import Price as v2024_12_18_acacia_price
    from .v2024_12_18_acacia.models import ProductModel as v2024_12_18_acacia_product
    from .v2024_12_18_acacia.models import (
        Subscription as v2024_12_18_acacia_subscription,
    )
    from .v2024_12_18_acacia.models.checkout import (
        Session as v2024_12_18_acacia_checkout_session,
    )
    from .v2025_01_27_acacia.models import ChargeModel as v2025_01_27_acacia_charge
    from .v2025_01_27_acacia.models import CustomerModel as v2025_01_27_acacia_customer
    from .v2025_01_27_acacia.models import Event as v2025_01_27_acacia_event
    from .v2025_01_27_acacia.models import InvoiceModel as v2025_01_27_acacia_invoice
    from .v2025_01_27_acacia.models import (
        PaymentIntent as v2025_01_27_acacia_payment_intent,
    )
    from .v2025_01_27_acacia.models import Price as v2025_01_27_acacia_price
    from .v2025_01_27_acacia.models import ProductModel as v2025_01_27_acacia_product
    from .v2025_01_27_acacia.models import (
        Subscription as v2025_01_27_acacia_subscription,
    )
    from .v2025_01_27_acacia.models.checkout import (
        Session as v2025_01_27_acacia_checkout_session,
    )
    from .v2025_02_24_acacia.models import ChargeModel as v2025_02_24_acacia_charge
    from .v2025_02_24_acacia.models import CustomerModel as v2025_02_24_acacia_customer
    from .v2025_02_24_acacia.models import Event as v2025_02_24_acacia_event
    from .v2025_02_24_acacia.models import InvoiceModel as v2025_02_24_acacia_invoice
    from .v2025_02_24_acacia.models import (
        PaymentIntent as v2025_02_24_acacia_payment_intent,
    )
    from .v2025_02_24_acacia.models import Price as v2025_02_24_acacia_price
    from .v2025_02_24_acacia.models import ProductModel as v2025_02_24_acacia_product
    from .v2025_02_24_acacia.models import (
        Subscription as v2025_02_24_acacia_subscription,
    )
    from .v2025_02_24_acacia.models.checkout import (
        Session as v2025_02_24_acacia_checkout_session,
    )
    from .v2025_03_31_basil.models import ChargeModel as v2025_03_31_basil_charge
    from .v2025_03_31_basil.models import CustomerModel as v2025_03_31_basil_customer
    from .v2025_03_31_basil.models import Event as v2025_03_31_basil_event
    from .v2025_03_31_basil.models import InvoiceModel as v2025_03_31_basil_invoice
    from .v2025_03_31_basil.models import (
        PaymentIntent as v2025_03_31_basil_payment_intent,
    )
    from .v2025_03_31_basil.models import Price as v2025_03_31_basil_price
    from .v2025_03_31_basil.models import ProductModel as v2025_03_31_basil_product
    from .v2025_03_31_basil.models import (
        SubscriptionModel as v2025_03_31_basil_subscription,
    )
    from .v2025_03_31_basil.models.checkout import (
        Session as v2025_03_31_basil_checkout_session,
    )
    from .v2025_04_30_basil.models import ChargeModel as v2025_04_30_basil_charge
    from .v2025_04_30_basil.models import CustomerModel as v2025_04_30_basil_customer
    from .v2025_04_30_basil.models import Event as v2025_04_30_basil_event
    from .v2025_04_30_basil.models import InvoiceModel as v2025_04_30_basil_invoice
    from .v2025_04_30_basil.models import (
        PaymentIntent as v2025_04_30_basil_payment_intent,
    )
    from .v2025_04_30_basil.models import Price as v2025_04_30_basil_price
    from .v2025_04_30_basil.models import ProductModel as v2025_04_30_basil_product
    from .v2025_04_30_basil.models import (
        SubscriptionModel as v2025_04_30_basil_subscription,
    )
    from .v2025_04_30_basil.models.checkout import (
        Session as v2025_04_30_basil_checkout_session,
    )
    from .v2025_05_28_basil.models import ChargeModel as v2025_05_28_basil_charge
    from .v2025_05_28_basil.models import CustomerModel as v2025_05_28_basil_customer
    from .v2025_05_28_basil.models import Event as v2025_05_28_basil_event
    from .v2025_05_28_basil.models import InvoiceModel as v2025_05_28_basil_invoice
    from .v2025_05_28_basil.models import (
        PaymentIntent as v2025_05_28_basil_payment_intent,
    )
    from .v2025_05_28_basil.models import Price as v2025_05_28_basil_price
    from .v2025_05_28_basil.models import ProductModel as v2025_05_28_basil_product
    from .v2025_05_28_basil.models import (
        SubscriptionModel as v2025_05_28_basil_subscription,
    )
    from .v2025_05_28_basil.models.checkout import (
        Session as v2025_05_28_basil_checkout_session,
    )
    from .v2025_06_30_basil.models import ChargeModel as v2025_06_30_basil_charge
    from .v2025_06_30_basil.models import CustomerModel as v2025_06_30_basil_customer
    from .v2025_06_30_basil.models import Event as v2025_06_30_basil_event
    from .v2025_06_30_basil.models import InvoiceModel as v2025_06_30_basil_invoice
    from .v2025_06_30_basil.models import (
        PaymentIntent as v2025_06_30_basil_payment_intent,
    )
    from .v2025_06_30_basil.models import Price as v2025_06_30_basil_price
    from .v2025_06_30_basil.models import ProductModel as v2025_06_30_basil_product
    from .v2025_06_30_basil.models import (
        SubscriptionModel as v2025_06_30_basil_subscription,
    )
    from .v2025_06_30_basil.models.checkout import (
        Session as v2025_06_30_basil_checkout_session,
    )
    from .v2025_07_30_basil.models import ChargeModel as v2025_07_30_basil_charge
    from .v2025_07_30_basil.models import CustomerModel as v2025_07_30_basil_customer
    from .v2025_07_30_basil.models import Event as v2025_07_30_basil_event
    from .v2025_07_30_basil.models import InvoiceModel as v2025_07_30_basil_invoice
    from .v2025_07_30_basil.models import (
        PaymentIntent as v2025_07_30_basil_payment_intent,
    )
    from .v2025_07_30_basil.models import Price as v2025_07_30_basil_price
    from .v2025_07_30_basil.models import ProductModel as v2025_07_30_basil_product
    from .v2025_07_30_basil.models import (
        SubscriptionModel as v2025_07_30_basil_subscription,
    )
    from .v2025_07_30_basil.models.checkout import (
        Session as v2025_07_30_basil_checkout_session,
    )
    from .v2025_08_27_basil.models import ChargeModel as v2025_08_27_basil_charge
    from .v2025_08_27_basil.models import CustomerModel as v2025_08_27_basil_customer
    from .v2025_08_27_basil.models import Event as v2025_08_27_basil_event
    from .v2025_08_27_basil.models import InvoiceModel as v2025_08_27_basil_invoice
    from .v2025_08_27_basil.models import (
        PaymentIntent as v2025_08_27_basil_payment_intent,
    )
    from .v2025_08_27_basil.models import Price as v2025_08_27_basil_price
    from .v2025_08_27_basil.models import ProductModel as v2025_08_27_basil_product
    from .v2025_08_27_basil.models import (
        SubscriptionModel as v2025_08_27_basil_subscription,
    )
    from .v2025_08_27_basil.models.checkout import (
        Session as v2025_08_27_basil_checkout_session,
    )
    from .v2025_09_30_clover.models import ChargeModel as v2025_09_30_clover_charge
    from .v2025_09_30_clover.models import CustomerModel as v2025_09_30_clover_customer
    from .v2025_09_30_clover.models import Event as v2025_09_30_clover_event
    from .v2025_09_30_clover.models import InvoiceModel as v2025_09_30_clover_invoice
    from .v2025_09_30_clover.models import (
        PaymentIntent as v2025_09_30_clover_payment_intent,
    )
    from .v2025_09_30_clover.models import Price as v2025_09_30_clover_price
    from .v2025_09_30_clover.models import ProductModel as v2025_09_30_clover_product
    from .v2025_09_30_clover.models import (
        SubscriptionModel as v2025_09_30_clover_subscription,
    )
    from .v2025_09_30_clover.models.checkout import (
        Session as v2025_09_30_clover_checkout_session,
    )
    from .v2025_10_29_clover.models import ChargeModel as v2025_10_29_clover_charge
    from .v2025_10_29_clover.models import CustomerModel as v2025_10_29_clover_customer
    from .v2025_10_29_clover.models import Event as v2025_10_29_clover_event
    from .v2025_10_29_clover.models import InvoiceModel as v2025_10_29_clover_invoice
    from .v2025_10_29_clover.models import (
        PaymentIntent as v2025_10_29_clover_payment_intent,
    )
    from .v2025_10_29_clover.models import Price as v2025_10_29_clover_price
    from .v2025_10_29_clover.models import ProductModel as v2025_10_29_clover_product
    from .v2025_10_29_clover.models import (
        SubscriptionModel as v2025_10_29_clover_subscription,
    )
    from .v2025_10_29_clover.models.checkout import (
        Session as v2025_10_29_clover_checkout_session,
    )
    from .v2025_11_17_clover.models import ChargeModel as v2025_11_17_clover_charge
    from .v2025_11_17_clover.models import CustomerModel as v2025_11_17_clover_customer
    from .v2025_11_17_clover.models import Event as v2025_11_17_clover_event
    from .v2025_11_17_clover.models import InvoiceModel as v2025_11_17_clover_invoice
    from .v2025_11_17_clover.models import (
        PaymentIntent as v2025_11_17_clover_payment_intent,
    )
    from .v2025_11_17_clover.models import Price as v2025_11_17_clover_price
    from .v2025_11_17_clover.models import ProductModel as v2025_11_17_clover_product
    from .v2025_11_17_clover.models import (
        SubscriptionModel as v2025_11_17_clover_subscription,
    )
    from .v2025_11_17_clover.models.checkout import (
        Session as v2025_11_17_clover_checkout_session,
    )
    from .v2025_12_15_clover.models import ChargeModel as v2025_12_15_clover_charge
    from .v2025_12_15_clover.models import CustomerModel as v2025_12_15_clover_customer
    from .v2025_12_15_clover.models import Event as v2025_12_15_clover_event
    from .v2025_12_15_clover.models import InvoiceModel as v2025_12_15_clover_invoice
    from .v2025_12_15_clover.models import (
        PaymentIntent as v2025_12_15_clover_payment_intent,
    )
    from .v2025_12_15_clover.models import PriceModel as v2025_12_15_clover_price
    from .v2025_12_15_clover.models import ProductModel as v2025_12_15_clover_product
    from .v2025_12_15_clover.models import (
        SubscriptionModel as v2025_12_15_clover_subscription,
    )
    from .v2025_12_15_clover.models.checkout import (
        Session as v2025_12_15_clover_checkout_session,
    )
    from .v2026_01_28_clover.models import ChargeModel as v2026_01_28_clover_charge
    from .v2026_01_28_clover.models import CustomerModel as v2026_01_28_clover_customer
    from .v2026_01_28_clover.models import Event as v2026_01_28_clover_event
    from .v2026_01_28_clover.models import InvoiceModel as v2026_01_28_clover_invoice
    from .v2026_01_28_clover.models import (
        PaymentIntent as v2026_01_28_clover_payment_intent,
    )
    from .v2026_01_28_clover.models import PriceModel as v2026_01_28_clover_price
    from .v2026_01_28_clover.models import ProductModel as v2026_01_28_clover_product
    from .v2026_01_28_clover.models import (
        SubscriptionModel as v2026_01_28_clover_subscription,
    )
    from .v2026_01_28_clover.models.checkout import (
        Session as v2026_01_28_clover_checkout_session,
    )
    from .v2026_02_25_clover.models import ChargeModel as v2026_02_25_clover_charge
    from .v2026_02_25_clover.models import CustomerModel as v2026_02_25_clover_customer
    from .v2026_02_25_clover.models import Event as v2026_02_25_clover_event
    from .v2026_02_25_clover.models import InvoiceModel as v2026_02_25_clover_invoice
    from .v2026_02_25_clover.models import (
        PaymentIntent as v2026_02_25_clover_payment_intent,
    )
    from .v2026_02_25_clover.models import PriceModel as v2026_02_25_clover_price
    from .v2026_02_25_clover.models import ProductModel as v2026_02_25_clover_product
    from .v2026_02_25_clover.models import (
        SubscriptionModel as v2026_02_25_clover_subscription,
    )
    from .v2026_02_25_clover.models.checkout import (
        Session as v2026_02_25_clover_checkout_session,
    )
    from .v2026_03_25_dahlia.models import ChargeModel as v2026_03_25_dahlia_charge
    from .v2026_03_25_dahlia.models import CustomerModel as v2026_03_25_dahlia_customer
    from .v2026_03_25_dahlia.models import Event as v2026_03_25_dahlia_event
    from .v2026_03_25_dahlia.models import InvoiceModel as v2026_03_25_dahlia_invoice
    from .v2026_03_25_dahlia.models import (
        PaymentIntent as v2026_03_25_dahlia_payment_intent,
    )
    from .v2026_03_25_dahlia.models import PriceModel as v2026_03_25_dahlia_price
    from .v2026_03_25_dahlia.models import ProductModel as v2026_03_25_dahlia_product
    from .v2026_03_25_dahlia.models import (
        SubscriptionModel as v2026_03_25_dahlia_subscription,
    )
    from .v2026_03_25_dahlia.models.checkout import (
        Session as v2026_03_25_dahlia_checkout_session,
    )

    StripeEventPayload: TypeAlias = (
        v2023_08_16_event
        | v2024_04_03_event
        | v2023_10_16_event
        | v2024_04_10_event
        | v2024_06_20_event
        | v2024_09_30_acacia_event
        | v2024_10_28_acacia_event
        | v2024_11_20_acacia_event
        | v2024_12_18_acacia_event
        | v2025_01_27_acacia_event
        | v2025_02_24_acacia_event
        | v2025_03_31_basil_event
        | v2025_04_30_basil_event
        | v2025_05_28_basil_event
        | v2025_06_30_basil_event
        | v2025_07_30_basil_event
        | v2025_08_27_basil_event
        | v2025_09_30_clover_event
        | v2025_10_29_clover_event
        | v2025_11_17_clover_event
        | v2025_12_15_clover_event
        | v2026_01_28_clover_event
        | v2026_02_25_clover_event
        | v2026_03_25_dahlia_event
    )

    StripeChargePayload: TypeAlias = (
        v2023_08_16_charge
        | v2024_04_03_charge
        | v2023_10_16_charge
        | v2024_04_10_charge
        | v2024_06_20_charge
        | v2024_09_30_acacia_charge
        | v2024_10_28_acacia_charge
        | v2024_11_20_acacia_charge
        | v2024_12_18_acacia_charge
        | v2025_01_27_acacia_charge
        | v2025_02_24_acacia_charge
        | v2025_03_31_basil_charge
        | v2025_04_30_basil_charge
        | v2025_05_28_basil_charge
        | v2025_06_30_basil_charge
        | v2025_07_30_basil_charge
        | v2025_08_27_basil_charge
        | v2025_09_30_clover_charge
        | v2025_10_29_clover_charge
        | v2025_11_17_clover_charge
        | v2025_12_15_clover_charge
        | v2026_01_28_clover_charge
        | v2026_02_25_clover_charge
        | v2026_03_25_dahlia_charge
        | None
    )

    StripeCheckoutSessionPayload: TypeAlias = (
        v2023_08_16_checkout_session
        | v2024_04_03_checkout_session
        | v2023_10_16_checkout_session
        | v2024_04_10_checkout_session
        | v2024_06_20_checkout_session
        | v2024_09_30_acacia_checkout_session
        | v2024_10_28_acacia_checkout_session
        | v2024_11_20_acacia_checkout_session
        | v2024_12_18_acacia_checkout_session
        | v2025_01_27_acacia_checkout_session
        | v2025_02_24_acacia_checkout_session
        | v2025_03_31_basil_checkout_session
        | v2025_04_30_basil_checkout_session
        | v2025_05_28_basil_checkout_session
        | v2025_06_30_basil_checkout_session
        | v2025_07_30_basil_checkout_session
        | v2025_08_27_basil_checkout_session
        | v2025_09_30_clover_checkout_session
        | v2025_10_29_clover_checkout_session
        | v2025_11_17_clover_checkout_session
        | v2025_12_15_clover_checkout_session
        | v2026_01_28_clover_checkout_session
        | v2026_02_25_clover_checkout_session
        | v2026_03_25_dahlia_checkout_session
        | None
    )

    StripeCustomerPayload: TypeAlias = (
        v2023_08_16_customer
        | v2024_04_03_customer
        | v2023_10_16_customer
        | v2024_04_10_customer
        | v2024_06_20_customer
        | v2024_09_30_acacia_customer
        | v2024_10_28_acacia_customer
        | v2024_11_20_acacia_customer
        | v2024_12_18_acacia_customer
        | v2025_01_27_acacia_customer
        | v2025_02_24_acacia_customer
        | v2025_03_31_basil_customer
        | v2025_04_30_basil_customer
        | v2025_05_28_basil_customer
        | v2025_06_30_basil_customer
        | v2025_07_30_basil_customer
        | v2025_08_27_basil_customer
        | v2025_09_30_clover_customer
        | v2025_10_29_clover_customer
        | v2025_11_17_clover_customer
        | v2025_12_15_clover_customer
        | v2026_01_28_clover_customer
        | v2026_02_25_clover_customer
        | v2026_03_25_dahlia_customer
        | None
    )

    StripeInvoicePayload: TypeAlias = (
        v2023_08_16_invoice
        | v2024_04_03_invoice
        | v2023_10_16_invoice
        | v2024_04_10_invoice
        | v2024_06_20_invoice
        | v2024_09_30_acacia_invoice
        | v2024_10_28_acacia_invoice
        | v2024_11_20_acacia_invoice
        | v2024_12_18_acacia_invoice
        | v2025_01_27_acacia_invoice
        | v2025_02_24_acacia_invoice
        | v2025_03_31_basil_invoice
        | v2025_04_30_basil_invoice
        | v2025_05_28_basil_invoice
        | v2025_06_30_basil_invoice
        | v2025_07_30_basil_invoice
        | v2025_08_27_basil_invoice
        | v2025_09_30_clover_invoice
        | v2025_10_29_clover_invoice
        | v2025_11_17_clover_invoice
        | v2025_12_15_clover_invoice
        | v2026_01_28_clover_invoice
        | v2026_02_25_clover_invoice
        | v2026_03_25_dahlia_invoice
        | None
    )

    StripePaymentIntentPayload: TypeAlias = (
        v2023_08_16_payment_intent
        | v2024_04_03_payment_intent
        | v2023_10_16_payment_intent
        | v2024_04_10_payment_intent
        | v2024_06_20_payment_intent
        | v2024_09_30_acacia_payment_intent
        | v2024_10_28_acacia_payment_intent
        | v2024_11_20_acacia_payment_intent
        | v2024_12_18_acacia_payment_intent
        | v2025_01_27_acacia_payment_intent
        | v2025_02_24_acacia_payment_intent
        | v2025_03_31_basil_payment_intent
        | v2025_04_30_basil_payment_intent
        | v2025_05_28_basil_payment_intent
        | v2025_06_30_basil_payment_intent
        | v2025_07_30_basil_payment_intent
        | v2025_08_27_basil_payment_intent
        | v2025_09_30_clover_payment_intent
        | v2025_10_29_clover_payment_intent
        | v2025_11_17_clover_payment_intent
        | v2025_12_15_clover_payment_intent
        | v2026_01_28_clover_payment_intent
        | v2026_02_25_clover_payment_intent
        | v2026_03_25_dahlia_payment_intent
        | None
    )

    StripePricePayload: TypeAlias = (
        v2023_08_16_price
        | v2024_04_03_price
        | v2023_10_16_price
        | v2024_04_10_price
        | v2024_06_20_price
        | v2024_09_30_acacia_price
        | v2024_10_28_acacia_price
        | v2024_11_20_acacia_price
        | v2024_12_18_acacia_price
        | v2025_01_27_acacia_price
        | v2025_02_24_acacia_price
        | v2025_03_31_basil_price
        | v2025_04_30_basil_price
        | v2025_05_28_basil_price
        | v2025_06_30_basil_price
        | v2025_07_30_basil_price
        | v2025_08_27_basil_price
        | v2025_09_30_clover_price
        | v2025_10_29_clover_price
        | v2025_11_17_clover_price
        | v2025_12_15_clover_price
        | v2026_01_28_clover_price
        | v2026_02_25_clover_price
        | v2026_03_25_dahlia_price
        | None
    )

    StripeProductPayload: TypeAlias = (
        v2023_08_16_product
        | v2024_04_03_product
        | v2023_10_16_product
        | v2024_04_10_product
        | v2024_06_20_product
        | v2024_09_30_acacia_product
        | v2024_10_28_acacia_product
        | v2024_11_20_acacia_product
        | v2024_12_18_acacia_product
        | v2025_01_27_acacia_product
        | v2025_02_24_acacia_product
        | v2025_03_31_basil_product
        | v2025_04_30_basil_product
        | v2025_05_28_basil_product
        | v2025_06_30_basil_product
        | v2025_07_30_basil_product
        | v2025_08_27_basil_product
        | v2025_09_30_clover_product
        | v2025_10_29_clover_product
        | v2025_11_17_clover_product
        | v2025_12_15_clover_product
        | v2026_01_28_clover_product
        | v2026_02_25_clover_product
        | v2026_03_25_dahlia_product
        | None
    )

    StripeSubscriptionPayload: TypeAlias = (
        v2023_08_16_subscription
        | v2024_04_03_subscription
        | v2023_10_16_subscription
        | v2024_04_10_subscription
        | v2024_06_20_subscription
        | v2024_09_30_acacia_subscription
        | v2024_10_28_acacia_subscription
        | v2024_11_20_acacia_subscription
        | v2024_12_18_acacia_subscription
        | v2025_01_27_acacia_subscription
        | v2025_02_24_acacia_subscription
        | v2025_03_31_basil_subscription
        | v2025_04_30_basil_subscription
        | v2025_05_28_basil_subscription
        | v2025_06_30_basil_subscription
        | v2025_07_30_basil_subscription
        | v2025_08_27_basil_subscription
        | v2025_09_30_clover_subscription
        | v2025_10_29_clover_subscription
        | v2025_11_17_clover_subscription
        | v2025_12_15_clover_subscription
        | v2026_01_28_clover_subscription
        | v2026_02_25_clover_subscription
        | v2026_03_25_dahlia_subscription
        | None
    )

    StripeObjectPayload: TypeAlias = (
        StripeChargePayload
        | StripeCheckoutSessionPayload
        | StripeCustomerPayload
        | StripeInvoicePayload
        | StripePaymentIntentPayload
        | StripePricePayload
        | StripeProductPayload
        | StripeSubscriptionPayload
    )
else:
    StripeObjectPayload = Any

_ADAPTERS: dict[str, LazyAdapter[Any]] = {
    "event": LazyAdapter(
        registry=_MODEL_REGISTRY["event"],
        discriminator_field=VERSION_DISCRIMINATOR_FIELD,
        package=__package__,
        label="event",
    ),
    "charge": LazyAdapter(
        registry=_MODEL_REGISTRY["charge"],
        discriminator_field=VERSION_DISCRIMINATOR_FIELD,
        package=__package__,
        label="charge",
    ),
    "checkout.session": LazyAdapter(
        registry=_MODEL_REGISTRY["checkout.session"],
        discriminator_field=VERSION_DISCRIMINATOR_FIELD,
        package=__package__,
        label="checkout.session",
    ),
    "customer": LazyAdapter(
        registry=_MODEL_REGISTRY["customer"],
        discriminator_field=VERSION_DISCRIMINATOR_FIELD,
        package=__package__,
        label="customer",
    ),
    "invoice": LazyAdapter(
        registry=_MODEL_REGISTRY["invoice"],
        discriminator_field=VERSION_DISCRIMINATOR_FIELD,
        package=__package__,
        label="invoice",
    ),
    "payment_intent": LazyAdapter(
        registry=_MODEL_REGISTRY["payment_intent"],
        discriminator_field=VERSION_DISCRIMINATOR_FIELD,
        package=__package__,
        label="payment_intent",
    ),
    "price": LazyAdapter(
        registry=_MODEL_REGISTRY["price"],
        discriminator_field=VERSION_DISCRIMINATOR_FIELD,
        package=__package__,
        label="price",
    ),
    "product": LazyAdapter(
        registry=_MODEL_REGISTRY["product"],
        discriminator_field=VERSION_DISCRIMINATOR_FIELD,
        package=__package__,
        label="product",
    ),
    "subscription": LazyAdapter(
        registry=_MODEL_REGISTRY["subscription"],
        discriminator_field=VERSION_DISCRIMINATOR_FIELD,
        package=__package__,
        label="subscription",
    ),
}

StripeEventAdapter: LazyAdapter[StripeEventPayload] = _ADAPTERS["event"]

StripeChargeAdapter: LazyAdapter[StripeChargePayload] = _ADAPTERS["charge"]

StripeCheckoutSessionAdapter: LazyAdapter[StripeCheckoutSessionPayload] = _ADAPTERS[
    "checkout.session"
]

StripeCustomerAdapter: LazyAdapter[StripeCustomerPayload] = _ADAPTERS["customer"]

StripeInvoiceAdapter: LazyAdapter[StripeInvoicePayload] = _ADAPTERS["invoice"]

StripePaymentIntentAdapter: LazyAdapter[StripePaymentIntentPayload] = _ADAPTERS[
    "payment_intent"
]

StripePriceAdapter: LazyAdapter[StripePricePayload] = _ADAPTERS["price"]

StripeProductAdapter: LazyAdapter[StripeProductPayload] = _ADAPTERS["product"]

StripeSubscriptionAdapter: LazyAdapter[StripeSubscriptionPayload] = _ADAPTERS[
    "subscription"
]

if not TYPE_CHECKING:
    StripeEventPayload = make_lazy_payload_type(
        "StripeEventPayload",
        StripeEventAdapter,
        module_name=__name__,
    )

    StripeChargePayload = make_lazy_payload_type(
        "StripeChargePayload",
        StripeChargeAdapter,
        module_name=__name__,
        nullable=True,
    )

    StripeCheckoutSessionPayload = make_lazy_payload_type(
        "StripeCheckoutSessionPayload",
        StripeCheckoutSessionAdapter,
        module_name=__name__,
        nullable=True,
    )

    StripeCustomerPayload = make_lazy_payload_type(
        "StripeCustomerPayload",
        StripeCustomerAdapter,
        module_name=__name__,
        nullable=True,
    )

    StripeInvoicePayload = make_lazy_payload_type(
        "StripeInvoicePayload",
        StripeInvoiceAdapter,
        module_name=__name__,
        nullable=True,
    )

    StripePaymentIntentPayload = make_lazy_payload_type(
        "StripePaymentIntentPayload",
        StripePaymentIntentAdapter,
        module_name=__name__,
        nullable=True,
    )

    StripePricePayload = make_lazy_payload_type(
        "StripePricePayload",
        StripePriceAdapter,
        module_name=__name__,
        nullable=True,
    )

    StripeProductPayload = make_lazy_payload_type(
        "StripeProductPayload",
        StripeProductAdapter,
        module_name=__name__,
        nullable=True,
    )

    StripeSubscriptionPayload = make_lazy_payload_type(
        "StripeSubscriptionPayload",
        StripeSubscriptionAdapter,
        module_name=__name__,
        nullable=True,
    )

__all__ = [
    "StripeEventPayload",
    "StripeChargePayload",
    "StripeCheckoutSessionPayload",
    "StripeCustomerPayload",
    "StripeInvoicePayload",
    "StripePaymentIntentPayload",
    "StripePricePayload",
    "StripeProductPayload",
    "StripeSubscriptionPayload",
    "StripeObjectPayload",
    "LazyAdapter",
    "LazyStripeAdapter",
    "StripeEventAdapter",
    "StripeChargeAdapter",
    "StripeCheckoutSessionAdapter",
    "StripeCustomerAdapter",
    "StripeInvoiceAdapter",
    "StripePaymentIntentAdapter",
    "StripePriceAdapter",
    "StripeProductAdapter",
    "StripeSubscriptionAdapter",
]
