# ruff: noqa: I001
from __future__ import annotations

from typing import Annotated, TypeAlias

from pydantic import Field, TypeAdapter

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
from .v2024_09_30_acacia.models import PaymentIntent as v2024_09_30_acacia_payment_intent
from .v2024_09_30_acacia.models import Price as v2024_09_30_acacia_price
from .v2024_09_30_acacia.models import ProductModel as v2024_09_30_acacia_product
from .v2024_09_30_acacia.models import Subscription as v2024_09_30_acacia_subscription
from .v2024_09_30_acacia.models.checkout import Session as v2024_09_30_acacia_checkout_session
from .v2024_10_28_acacia.models import ChargeModel as v2024_10_28_acacia_charge
from .v2024_10_28_acacia.models import CustomerModel as v2024_10_28_acacia_customer
from .v2024_10_28_acacia.models import Event as v2024_10_28_acacia_event
from .v2024_10_28_acacia.models import InvoiceModel as v2024_10_28_acacia_invoice
from .v2024_10_28_acacia.models import PaymentIntent as v2024_10_28_acacia_payment_intent
from .v2024_10_28_acacia.models import Price as v2024_10_28_acacia_price
from .v2024_10_28_acacia.models import ProductModel as v2024_10_28_acacia_product
from .v2024_10_28_acacia.models import Subscription as v2024_10_28_acacia_subscription
from .v2024_10_28_acacia.models.checkout import Session as v2024_10_28_acacia_checkout_session
from .v2024_11_20_acacia.models import ChargeModel as v2024_11_20_acacia_charge
from .v2024_11_20_acacia.models import CustomerModel as v2024_11_20_acacia_customer
from .v2024_11_20_acacia.models import Event as v2024_11_20_acacia_event
from .v2024_11_20_acacia.models import InvoiceModel as v2024_11_20_acacia_invoice
from .v2024_11_20_acacia.models import PaymentIntent as v2024_11_20_acacia_payment_intent
from .v2024_11_20_acacia.models import Price as v2024_11_20_acacia_price
from .v2024_11_20_acacia.models import ProductModel as v2024_11_20_acacia_product
from .v2024_11_20_acacia.models import Subscription as v2024_11_20_acacia_subscription
from .v2024_11_20_acacia.models.checkout import Session as v2024_11_20_acacia_checkout_session
from .v2024_12_18_acacia.models import ChargeModel as v2024_12_18_acacia_charge
from .v2024_12_18_acacia.models import CustomerModel as v2024_12_18_acacia_customer
from .v2024_12_18_acacia.models import Event as v2024_12_18_acacia_event
from .v2024_12_18_acacia.models import InvoiceModel as v2024_12_18_acacia_invoice
from .v2024_12_18_acacia.models import PaymentIntent as v2024_12_18_acacia_payment_intent
from .v2024_12_18_acacia.models import Price as v2024_12_18_acacia_price
from .v2024_12_18_acacia.models import ProductModel as v2024_12_18_acacia_product
from .v2024_12_18_acacia.models import Subscription as v2024_12_18_acacia_subscription
from .v2024_12_18_acacia.models.checkout import Session as v2024_12_18_acacia_checkout_session
from .v2025_01_27_acacia.models import ChargeModel as v2025_01_27_acacia_charge
from .v2025_01_27_acacia.models import CustomerModel as v2025_01_27_acacia_customer
from .v2025_01_27_acacia.models import Event as v2025_01_27_acacia_event
from .v2025_01_27_acacia.models import InvoiceModel as v2025_01_27_acacia_invoice
from .v2025_01_27_acacia.models import PaymentIntent as v2025_01_27_acacia_payment_intent
from .v2025_01_27_acacia.models import Price as v2025_01_27_acacia_price
from .v2025_01_27_acacia.models import ProductModel as v2025_01_27_acacia_product
from .v2025_01_27_acacia.models import Subscription as v2025_01_27_acacia_subscription
from .v2025_01_27_acacia.models.checkout import Session as v2025_01_27_acacia_checkout_session
from .v2025_02_24_acacia.models import ChargeModel as v2025_02_24_acacia_charge
from .v2025_02_24_acacia.models import CustomerModel as v2025_02_24_acacia_customer
from .v2025_02_24_acacia.models import Event as v2025_02_24_acacia_event
from .v2025_02_24_acacia.models import InvoiceModel as v2025_02_24_acacia_invoice
from .v2025_02_24_acacia.models import PaymentIntent as v2025_02_24_acacia_payment_intent
from .v2025_02_24_acacia.models import Price as v2025_02_24_acacia_price
from .v2025_02_24_acacia.models import ProductModel as v2025_02_24_acacia_product
from .v2025_02_24_acacia.models import Subscription as v2025_02_24_acacia_subscription
from .v2025_02_24_acacia.models.checkout import Session as v2025_02_24_acacia_checkout_session
from .v2025_03_31_basil.models import ChargeModel as v2025_03_31_basil_charge
from .v2025_03_31_basil.models import CustomerModel as v2025_03_31_basil_customer
from .v2025_03_31_basil.models import Event as v2025_03_31_basil_event
from .v2025_03_31_basil.models import InvoiceModel as v2025_03_31_basil_invoice
from .v2025_03_31_basil.models import PaymentIntent as v2025_03_31_basil_payment_intent
from .v2025_03_31_basil.models import Price as v2025_03_31_basil_price
from .v2025_03_31_basil.models import ProductModel as v2025_03_31_basil_product
from .v2025_03_31_basil.models import SubscriptionModel as v2025_03_31_basil_subscription
from .v2025_03_31_basil.models.checkout import Session as v2025_03_31_basil_checkout_session
from .v2025_04_30_basil.models import ChargeModel as v2025_04_30_basil_charge
from .v2025_04_30_basil.models import CustomerModel as v2025_04_30_basil_customer
from .v2025_04_30_basil.models import Event as v2025_04_30_basil_event
from .v2025_04_30_basil.models import InvoiceModel as v2025_04_30_basil_invoice
from .v2025_04_30_basil.models import PaymentIntent as v2025_04_30_basil_payment_intent
from .v2025_04_30_basil.models import Price as v2025_04_30_basil_price
from .v2025_04_30_basil.models import ProductModel as v2025_04_30_basil_product
from .v2025_04_30_basil.models import SubscriptionModel as v2025_04_30_basil_subscription
from .v2025_04_30_basil.models.checkout import Session as v2025_04_30_basil_checkout_session
from .v2025_05_28_basil.models import ChargeModel as v2025_05_28_basil_charge
from .v2025_05_28_basil.models import CustomerModel as v2025_05_28_basil_customer
from .v2025_05_28_basil.models import Event as v2025_05_28_basil_event
from .v2025_05_28_basil.models import InvoiceModel as v2025_05_28_basil_invoice
from .v2025_05_28_basil.models import PaymentIntent as v2025_05_28_basil_payment_intent
from .v2025_05_28_basil.models import Price as v2025_05_28_basil_price
from .v2025_05_28_basil.models import ProductModel as v2025_05_28_basil_product
from .v2025_05_28_basil.models import SubscriptionModel as v2025_05_28_basil_subscription
from .v2025_05_28_basil.models.checkout import Session as v2025_05_28_basil_checkout_session
from .v2025_06_30_basil.models import ChargeModel as v2025_06_30_basil_charge
from .v2025_06_30_basil.models import CustomerModel as v2025_06_30_basil_customer
from .v2025_06_30_basil.models import Event as v2025_06_30_basil_event
from .v2025_06_30_basil.models import InvoiceModel as v2025_06_30_basil_invoice
from .v2025_06_30_basil.models import PaymentIntent as v2025_06_30_basil_payment_intent
from .v2025_06_30_basil.models import Price as v2025_06_30_basil_price
from .v2025_06_30_basil.models import ProductModel as v2025_06_30_basil_product
from .v2025_06_30_basil.models import SubscriptionModel as v2025_06_30_basil_subscription
from .v2025_06_30_basil.models.checkout import Session as v2025_06_30_basil_checkout_session
from .v2025_07_30_basil.models import ChargeModel as v2025_07_30_basil_charge
from .v2025_07_30_basil.models import CustomerModel as v2025_07_30_basil_customer
from .v2025_07_30_basil.models import Event as v2025_07_30_basil_event
from .v2025_07_30_basil.models import InvoiceModel as v2025_07_30_basil_invoice
from .v2025_07_30_basil.models import PaymentIntent as v2025_07_30_basil_payment_intent
from .v2025_07_30_basil.models import Price as v2025_07_30_basil_price
from .v2025_07_30_basil.models import ProductModel as v2025_07_30_basil_product
from .v2025_07_30_basil.models import SubscriptionModel as v2025_07_30_basil_subscription
from .v2025_07_30_basil.models.checkout import Session as v2025_07_30_basil_checkout_session
from .v2025_08_27_basil.models import ChargeModel as v2025_08_27_basil_charge
from .v2025_08_27_basil.models import CustomerModel as v2025_08_27_basil_customer
from .v2025_08_27_basil.models import Event as v2025_08_27_basil_event
from .v2025_08_27_basil.models import InvoiceModel as v2025_08_27_basil_invoice
from .v2025_08_27_basil.models import PaymentIntent as v2025_08_27_basil_payment_intent
from .v2025_08_27_basil.models import Price as v2025_08_27_basil_price
from .v2025_08_27_basil.models import ProductModel as v2025_08_27_basil_product
from .v2025_08_27_basil.models import SubscriptionModel as v2025_08_27_basil_subscription
from .v2025_08_27_basil.models.checkout import Session as v2025_08_27_basil_checkout_session
from .v2025_09_30_clover.models import ChargeModel as v2025_09_30_clover_charge
from .v2025_09_30_clover.models import CustomerModel as v2025_09_30_clover_customer
from .v2025_09_30_clover.models import Event as v2025_09_30_clover_event
from .v2025_09_30_clover.models import InvoiceModel as v2025_09_30_clover_invoice
from .v2025_09_30_clover.models import PaymentIntent as v2025_09_30_clover_payment_intent
from .v2025_09_30_clover.models import Price as v2025_09_30_clover_price
from .v2025_09_30_clover.models import ProductModel as v2025_09_30_clover_product
from .v2025_09_30_clover.models import SubscriptionModel as v2025_09_30_clover_subscription
from .v2025_09_30_clover.models.checkout import Session as v2025_09_30_clover_checkout_session
from .v2025_10_29_clover.models import ChargeModel as v2025_10_29_clover_charge
from .v2025_10_29_clover.models import CustomerModel as v2025_10_29_clover_customer
from .v2025_10_29_clover.models import Event as v2025_10_29_clover_event
from .v2025_10_29_clover.models import InvoiceModel as v2025_10_29_clover_invoice
from .v2025_10_29_clover.models import PaymentIntent as v2025_10_29_clover_payment_intent
from .v2025_10_29_clover.models import Price as v2025_10_29_clover_price
from .v2025_10_29_clover.models import ProductModel as v2025_10_29_clover_product
from .v2025_10_29_clover.models import SubscriptionModel as v2025_10_29_clover_subscription
from .v2025_10_29_clover.models.checkout import Session as v2025_10_29_clover_checkout_session
from .v2025_11_17_clover.models import ChargeModel as v2025_11_17_clover_charge
from .v2025_11_17_clover.models import CustomerModel as v2025_11_17_clover_customer
from .v2025_11_17_clover.models import Event as v2025_11_17_clover_event
from .v2025_11_17_clover.models import InvoiceModel as v2025_11_17_clover_invoice
from .v2025_11_17_clover.models import PaymentIntent as v2025_11_17_clover_payment_intent
from .v2025_11_17_clover.models import Price as v2025_11_17_clover_price
from .v2025_11_17_clover.models import ProductModel as v2025_11_17_clover_product
from .v2025_11_17_clover.models import SubscriptionModel as v2025_11_17_clover_subscription
from .v2025_11_17_clover.models.checkout import Session as v2025_11_17_clover_checkout_session
from .v2025_12_15_clover.models import ChargeModel as v2025_12_15_clover_charge
from .v2025_12_15_clover.models import CustomerModel as v2025_12_15_clover_customer
from .v2025_12_15_clover.models import Event as v2025_12_15_clover_event
from .v2025_12_15_clover.models import InvoiceModel as v2025_12_15_clover_invoice
from .v2025_12_15_clover.models import PaymentIntent as v2025_12_15_clover_payment_intent
from .v2025_12_15_clover.models import PriceModel as v2025_12_15_clover_price
from .v2025_12_15_clover.models import ProductModel as v2025_12_15_clover_product
from .v2025_12_15_clover.models import SubscriptionModel as v2025_12_15_clover_subscription
from .v2025_12_15_clover.models.checkout import Session as v2025_12_15_clover_checkout_session
from .v2026_01_28_clover.models import ChargeModel as v2026_01_28_clover_charge
from .v2026_01_28_clover.models import CustomerModel as v2026_01_28_clover_customer
from .v2026_01_28_clover.models import Event as v2026_01_28_clover_event
from .v2026_01_28_clover.models import InvoiceModel as v2026_01_28_clover_invoice
from .v2026_01_28_clover.models import PaymentIntent as v2026_01_28_clover_payment_intent
from .v2026_01_28_clover.models import PriceModel as v2026_01_28_clover_price
from .v2026_01_28_clover.models import ProductModel as v2026_01_28_clover_product
from .v2026_01_28_clover.models import SubscriptionModel as v2026_01_28_clover_subscription
from .v2026_01_28_clover.models.checkout import Session as v2026_01_28_clover_checkout_session
from .v2026_02_25_clover.models import ChargeModel as v2026_02_25_clover_charge
from .v2026_02_25_clover.models import CustomerModel as v2026_02_25_clover_customer
from .v2026_02_25_clover.models import Event as v2026_02_25_clover_event
from .v2026_02_25_clover.models import InvoiceModel as v2026_02_25_clover_invoice
from .v2026_02_25_clover.models import PaymentIntent as v2026_02_25_clover_payment_intent
from .v2026_02_25_clover.models import PriceModel as v2026_02_25_clover_price
from .v2026_02_25_clover.models import ProductModel as v2026_02_25_clover_product
from .v2026_02_25_clover.models import SubscriptionModel as v2026_02_25_clover_subscription
from .v2026_02_25_clover.models.checkout import Session as v2026_02_25_clover_checkout_session
from .v2026_03_25_dahlia.models import ChargeModel as v2026_03_25_dahlia_charge
from .v2026_03_25_dahlia.models import CustomerModel as v2026_03_25_dahlia_customer
from .v2026_03_25_dahlia.models import Event as v2026_03_25_dahlia_event
from .v2026_03_25_dahlia.models import InvoiceModel as v2026_03_25_dahlia_invoice
from .v2026_03_25_dahlia.models import PaymentIntent as v2026_03_25_dahlia_payment_intent
from .v2026_03_25_dahlia.models import PriceModel as v2026_03_25_dahlia_price
from .v2026_03_25_dahlia.models import ProductModel as v2026_03_25_dahlia_product
from .v2026_03_25_dahlia.models import SubscriptionModel as v2026_03_25_dahlia_subscription
from .v2026_03_25_dahlia.models.checkout import Session as v2026_03_25_dahlia_checkout_session

StripeEventPayload: TypeAlias = Annotated[
    v2023_08_16_event | v2024_04_03_event | v2023_10_16_event | v2024_04_10_event | v2024_06_20_event | v2024_09_30_acacia_event | v2024_10_28_acacia_event | v2024_11_20_acacia_event | v2024_12_18_acacia_event | v2025_01_27_acacia_event | v2025_02_24_acacia_event | v2025_03_31_basil_event | v2025_04_30_basil_event | v2025_05_28_basil_event | v2025_06_30_basil_event | v2025_07_30_basil_event | v2025_08_27_basil_event | v2025_09_30_clover_event | v2025_10_29_clover_event | v2025_11_17_clover_event | v2025_12_15_clover_event | v2026_01_28_clover_event | v2026_02_25_clover_event | v2026_03_25_dahlia_event,
    Field(discriminator="mountaineer_billing_api_version"),
]
StripeEventAdapter = TypeAdapter(StripeEventPayload)

StripeChargePayload: TypeAlias = Annotated[
    v2023_08_16_charge | v2024_04_03_charge | v2023_10_16_charge | v2024_04_10_charge | v2024_06_20_charge | v2024_09_30_acacia_charge | v2024_10_28_acacia_charge | v2024_11_20_acacia_charge | v2024_12_18_acacia_charge | v2025_01_27_acacia_charge | v2025_02_24_acacia_charge | v2025_03_31_basil_charge | v2025_04_30_basil_charge | v2025_05_28_basil_charge | v2025_06_30_basil_charge | v2025_07_30_basil_charge | v2025_08_27_basil_charge | v2025_09_30_clover_charge | v2025_10_29_clover_charge | v2025_11_17_clover_charge | v2025_12_15_clover_charge | v2026_01_28_clover_charge | v2026_02_25_clover_charge | v2026_03_25_dahlia_charge,
    Field(discriminator="mountaineer_billing_api_version"),
]
StripeChargeAdapter = TypeAdapter(StripeChargePayload)

StripeCheckoutSessionPayload: TypeAlias = Annotated[
    v2023_08_16_checkout_session | v2024_04_03_checkout_session | v2023_10_16_checkout_session | v2024_04_10_checkout_session | v2024_06_20_checkout_session | v2024_09_30_acacia_checkout_session | v2024_10_28_acacia_checkout_session | v2024_11_20_acacia_checkout_session | v2024_12_18_acacia_checkout_session | v2025_01_27_acacia_checkout_session | v2025_02_24_acacia_checkout_session | v2025_03_31_basil_checkout_session | v2025_04_30_basil_checkout_session | v2025_05_28_basil_checkout_session | v2025_06_30_basil_checkout_session | v2025_07_30_basil_checkout_session | v2025_08_27_basil_checkout_session | v2025_09_30_clover_checkout_session | v2025_10_29_clover_checkout_session | v2025_11_17_clover_checkout_session | v2025_12_15_clover_checkout_session | v2026_01_28_clover_checkout_session | v2026_02_25_clover_checkout_session | v2026_03_25_dahlia_checkout_session,
    Field(discriminator="mountaineer_billing_api_version"),
]
StripeCheckoutSessionAdapter = TypeAdapter(StripeCheckoutSessionPayload)

StripeCustomerPayload: TypeAlias = Annotated[
    v2023_08_16_customer | v2024_04_03_customer | v2023_10_16_customer | v2024_04_10_customer | v2024_06_20_customer | v2024_09_30_acacia_customer | v2024_10_28_acacia_customer | v2024_11_20_acacia_customer | v2024_12_18_acacia_customer | v2025_01_27_acacia_customer | v2025_02_24_acacia_customer | v2025_03_31_basil_customer | v2025_04_30_basil_customer | v2025_05_28_basil_customer | v2025_06_30_basil_customer | v2025_07_30_basil_customer | v2025_08_27_basil_customer | v2025_09_30_clover_customer | v2025_10_29_clover_customer | v2025_11_17_clover_customer | v2025_12_15_clover_customer | v2026_01_28_clover_customer | v2026_02_25_clover_customer | v2026_03_25_dahlia_customer,
    Field(discriminator="mountaineer_billing_api_version"),
]
StripeCustomerAdapter = TypeAdapter(StripeCustomerPayload)

StripeInvoicePayload: TypeAlias = Annotated[
    v2023_08_16_invoice | v2024_04_03_invoice | v2023_10_16_invoice | v2024_04_10_invoice | v2024_06_20_invoice | v2024_09_30_acacia_invoice | v2024_10_28_acacia_invoice | v2024_11_20_acacia_invoice | v2024_12_18_acacia_invoice | v2025_01_27_acacia_invoice | v2025_02_24_acacia_invoice | v2025_03_31_basil_invoice | v2025_04_30_basil_invoice | v2025_05_28_basil_invoice | v2025_06_30_basil_invoice | v2025_07_30_basil_invoice | v2025_08_27_basil_invoice | v2025_09_30_clover_invoice | v2025_10_29_clover_invoice | v2025_11_17_clover_invoice | v2025_12_15_clover_invoice | v2026_01_28_clover_invoice | v2026_02_25_clover_invoice | v2026_03_25_dahlia_invoice,
    Field(discriminator="mountaineer_billing_api_version"),
]
StripeInvoiceAdapter = TypeAdapter(StripeInvoicePayload)

StripePaymentIntentPayload: TypeAlias = Annotated[
    v2023_08_16_payment_intent | v2024_04_03_payment_intent | v2023_10_16_payment_intent | v2024_04_10_payment_intent | v2024_06_20_payment_intent | v2024_09_30_acacia_payment_intent | v2024_10_28_acacia_payment_intent | v2024_11_20_acacia_payment_intent | v2024_12_18_acacia_payment_intent | v2025_01_27_acacia_payment_intent | v2025_02_24_acacia_payment_intent | v2025_03_31_basil_payment_intent | v2025_04_30_basil_payment_intent | v2025_05_28_basil_payment_intent | v2025_06_30_basil_payment_intent | v2025_07_30_basil_payment_intent | v2025_08_27_basil_payment_intent | v2025_09_30_clover_payment_intent | v2025_10_29_clover_payment_intent | v2025_11_17_clover_payment_intent | v2025_12_15_clover_payment_intent | v2026_01_28_clover_payment_intent | v2026_02_25_clover_payment_intent | v2026_03_25_dahlia_payment_intent,
    Field(discriminator="mountaineer_billing_api_version"),
]
StripePaymentIntentAdapter = TypeAdapter(StripePaymentIntentPayload)

StripePricePayload: TypeAlias = Annotated[
    v2023_08_16_price | v2024_04_03_price | v2023_10_16_price | v2024_04_10_price | v2024_06_20_price | v2024_09_30_acacia_price | v2024_10_28_acacia_price | v2024_11_20_acacia_price | v2024_12_18_acacia_price | v2025_01_27_acacia_price | v2025_02_24_acacia_price | v2025_03_31_basil_price | v2025_04_30_basil_price | v2025_05_28_basil_price | v2025_06_30_basil_price | v2025_07_30_basil_price | v2025_08_27_basil_price | v2025_09_30_clover_price | v2025_10_29_clover_price | v2025_11_17_clover_price | v2025_12_15_clover_price | v2026_01_28_clover_price | v2026_02_25_clover_price | v2026_03_25_dahlia_price,
    Field(discriminator="mountaineer_billing_api_version"),
]
StripePriceAdapter = TypeAdapter(StripePricePayload)

StripeProductPayload: TypeAlias = Annotated[
    v2023_08_16_product | v2024_04_03_product | v2023_10_16_product | v2024_04_10_product | v2024_06_20_product | v2024_09_30_acacia_product | v2024_10_28_acacia_product | v2024_11_20_acacia_product | v2024_12_18_acacia_product | v2025_01_27_acacia_product | v2025_02_24_acacia_product | v2025_03_31_basil_product | v2025_04_30_basil_product | v2025_05_28_basil_product | v2025_06_30_basil_product | v2025_07_30_basil_product | v2025_08_27_basil_product | v2025_09_30_clover_product | v2025_10_29_clover_product | v2025_11_17_clover_product | v2025_12_15_clover_product | v2026_01_28_clover_product | v2026_02_25_clover_product | v2026_03_25_dahlia_product,
    Field(discriminator="mountaineer_billing_api_version"),
]
StripeProductAdapter = TypeAdapter(StripeProductPayload)

StripeSubscriptionPayload: TypeAlias = Annotated[
    v2023_08_16_subscription | v2024_04_03_subscription | v2023_10_16_subscription | v2024_04_10_subscription | v2024_06_20_subscription | v2024_09_30_acacia_subscription | v2024_10_28_acacia_subscription | v2024_11_20_acacia_subscription | v2024_12_18_acacia_subscription | v2025_01_27_acacia_subscription | v2025_02_24_acacia_subscription | v2025_03_31_basil_subscription | v2025_04_30_basil_subscription | v2025_05_28_basil_subscription | v2025_06_30_basil_subscription | v2025_07_30_basil_subscription | v2025_08_27_basil_subscription | v2025_09_30_clover_subscription | v2025_10_29_clover_subscription | v2025_11_17_clover_subscription | v2025_12_15_clover_subscription | v2026_01_28_clover_subscription | v2026_02_25_clover_subscription | v2026_03_25_dahlia_subscription,
    Field(discriminator="mountaineer_billing_api_version"),
]
StripeSubscriptionAdapter = TypeAdapter(StripeSubscriptionPayload)

StripeObjectPayload: TypeAlias = (
    StripeChargePayload | StripeCheckoutSessionPayload | StripeCustomerPayload | StripeInvoicePayload | StripePaymentIntentPayload | StripePricePayload | StripeProductPayload | StripeSubscriptionPayload
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
