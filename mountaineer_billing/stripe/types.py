# ruff: noqa: I001
from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeAlias, TypeVar, cast

from pydantic import BaseModel
from pydantic_core import core_schema

VERSION_DISCRIMINATOR_FIELD = "mountaineer_billing_api_version"

ValidatedStripeModel = TypeVar("ValidatedStripeModel")

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


class LazyStripeAdapter(Generic[ValidatedStripeModel]):
    def __init__(self, object_type: str):
        self.object_type = object_type
        self._registry = _MODEL_REGISTRY[object_type]
        self._model_cache: dict[str, type[BaseModel]] = {}

    def validate_python(self, value: Any) -> ValidatedStripeModel:
        if isinstance(value, BaseModel):
            api_version = getattr(value, VERSION_DISCRIMINATOR_FIELD, None)
            if isinstance(api_version, str) and api_version in self._registry:
                model_type = self._load_model(api_version)
                if isinstance(value, model_type):
                    return cast(ValidatedStripeModel, value)
            value = value.model_dump(mode="python")

        if not isinstance(value, Mapping):
            raise TypeError(
                f"Expected a mapping or BaseModel for {self.object_type!r}, got {type(value).__name__}"
            )

        api_version = value.get(VERSION_DISCRIMINATOR_FIELD)
        if not isinstance(api_version, str):
            raise ValueError(
                f"Stripe payload is missing a string {VERSION_DISCRIMINATOR_FIELD!r} discriminator"
            )

        model_type = self._load_model(api_version)
        return cast(ValidatedStripeModel, model_type.model_validate(value))

    def _load_model(self, api_version: str) -> type[BaseModel]:
        try:
            return self._model_cache[api_version]
        except KeyError:
            pass

        try:
            module_path, symbol_name = self._registry[api_version]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported Stripe API version {api_version!r} for {self.object_type!r}"
            ) from exc

        module = import_module(module_path, package=__package__)
        model_type = cast(type[BaseModel], getattr(module, symbol_name))
        self._model_cache[api_version] = model_type
        return model_type


def _serialize_validated_model(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


class _LazyStripePayloadBase:
    object_type: ClassVar[str]

    @classmethod
    def _adapter(cls) -> LazyStripeAdapter[Any]:
        return _ADAPTERS[cls.object_type]

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: Any,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(
            cls._adapter().validate_python,
            serialization=core_schema.plain_serializer_function_ser_schema(
                _serialize_validated_model,
                return_schema=core_schema.any_schema(),
                when_used="always",
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema_value: core_schema.CoreSchema,
        handler: Any,
    ) -> dict[str, Any]:
        return {
            "type": "object",
            "title": f"{cls.__name__}",
        }


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

    StripeEventPayload: TypeAlias = (
        v2023_08_16_event | v2024_04_03_event | v2023_10_16_event | v2024_04_10_event | v2024_06_20_event | v2024_09_30_acacia_event | v2024_10_28_acacia_event | v2024_11_20_acacia_event | v2024_12_18_acacia_event | v2025_01_27_acacia_event | v2025_02_24_acacia_event | v2025_03_31_basil_event | v2025_04_30_basil_event | v2025_05_28_basil_event | v2025_06_30_basil_event | v2025_07_30_basil_event | v2025_08_27_basil_event | v2025_09_30_clover_event | v2025_10_29_clover_event | v2025_11_17_clover_event | v2025_12_15_clover_event | v2026_01_28_clover_event | v2026_02_25_clover_event | v2026_03_25_dahlia_event
    )

    StripeChargePayload: TypeAlias = (
        v2023_08_16_charge | v2024_04_03_charge | v2023_10_16_charge | v2024_04_10_charge | v2024_06_20_charge | v2024_09_30_acacia_charge | v2024_10_28_acacia_charge | v2024_11_20_acacia_charge | v2024_12_18_acacia_charge | v2025_01_27_acacia_charge | v2025_02_24_acacia_charge | v2025_03_31_basil_charge | v2025_04_30_basil_charge | v2025_05_28_basil_charge | v2025_06_30_basil_charge | v2025_07_30_basil_charge | v2025_08_27_basil_charge | v2025_09_30_clover_charge | v2025_10_29_clover_charge | v2025_11_17_clover_charge | v2025_12_15_clover_charge | v2026_01_28_clover_charge | v2026_02_25_clover_charge | v2026_03_25_dahlia_charge
    )

    StripeCheckoutSessionPayload: TypeAlias = (
        v2023_08_16_checkout_session | v2024_04_03_checkout_session | v2023_10_16_checkout_session | v2024_04_10_checkout_session | v2024_06_20_checkout_session | v2024_09_30_acacia_checkout_session | v2024_10_28_acacia_checkout_session | v2024_11_20_acacia_checkout_session | v2024_12_18_acacia_checkout_session | v2025_01_27_acacia_checkout_session | v2025_02_24_acacia_checkout_session | v2025_03_31_basil_checkout_session | v2025_04_30_basil_checkout_session | v2025_05_28_basil_checkout_session | v2025_06_30_basil_checkout_session | v2025_07_30_basil_checkout_session | v2025_08_27_basil_checkout_session | v2025_09_30_clover_checkout_session | v2025_10_29_clover_checkout_session | v2025_11_17_clover_checkout_session | v2025_12_15_clover_checkout_session | v2026_01_28_clover_checkout_session | v2026_02_25_clover_checkout_session | v2026_03_25_dahlia_checkout_session
    )

    StripeCustomerPayload: TypeAlias = (
        v2023_08_16_customer | v2024_04_03_customer | v2023_10_16_customer | v2024_04_10_customer | v2024_06_20_customer | v2024_09_30_acacia_customer | v2024_10_28_acacia_customer | v2024_11_20_acacia_customer | v2024_12_18_acacia_customer | v2025_01_27_acacia_customer | v2025_02_24_acacia_customer | v2025_03_31_basil_customer | v2025_04_30_basil_customer | v2025_05_28_basil_customer | v2025_06_30_basil_customer | v2025_07_30_basil_customer | v2025_08_27_basil_customer | v2025_09_30_clover_customer | v2025_10_29_clover_customer | v2025_11_17_clover_customer | v2025_12_15_clover_customer | v2026_01_28_clover_customer | v2026_02_25_clover_customer | v2026_03_25_dahlia_customer
    )

    StripeInvoicePayload: TypeAlias = (
        v2023_08_16_invoice | v2024_04_03_invoice | v2023_10_16_invoice | v2024_04_10_invoice | v2024_06_20_invoice | v2024_09_30_acacia_invoice | v2024_10_28_acacia_invoice | v2024_11_20_acacia_invoice | v2024_12_18_acacia_invoice | v2025_01_27_acacia_invoice | v2025_02_24_acacia_invoice | v2025_03_31_basil_invoice | v2025_04_30_basil_invoice | v2025_05_28_basil_invoice | v2025_06_30_basil_invoice | v2025_07_30_basil_invoice | v2025_08_27_basil_invoice | v2025_09_30_clover_invoice | v2025_10_29_clover_invoice | v2025_11_17_clover_invoice | v2025_12_15_clover_invoice | v2026_01_28_clover_invoice | v2026_02_25_clover_invoice | v2026_03_25_dahlia_invoice
    )

    StripePaymentIntentPayload: TypeAlias = (
        v2023_08_16_payment_intent | v2024_04_03_payment_intent | v2023_10_16_payment_intent | v2024_04_10_payment_intent | v2024_06_20_payment_intent | v2024_09_30_acacia_payment_intent | v2024_10_28_acacia_payment_intent | v2024_11_20_acacia_payment_intent | v2024_12_18_acacia_payment_intent | v2025_01_27_acacia_payment_intent | v2025_02_24_acacia_payment_intent | v2025_03_31_basil_payment_intent | v2025_04_30_basil_payment_intent | v2025_05_28_basil_payment_intent | v2025_06_30_basil_payment_intent | v2025_07_30_basil_payment_intent | v2025_08_27_basil_payment_intent | v2025_09_30_clover_payment_intent | v2025_10_29_clover_payment_intent | v2025_11_17_clover_payment_intent | v2025_12_15_clover_payment_intent | v2026_01_28_clover_payment_intent | v2026_02_25_clover_payment_intent | v2026_03_25_dahlia_payment_intent
    )

    StripePricePayload: TypeAlias = (
        v2023_08_16_price | v2024_04_03_price | v2023_10_16_price | v2024_04_10_price | v2024_06_20_price | v2024_09_30_acacia_price | v2024_10_28_acacia_price | v2024_11_20_acacia_price | v2024_12_18_acacia_price | v2025_01_27_acacia_price | v2025_02_24_acacia_price | v2025_03_31_basil_price | v2025_04_30_basil_price | v2025_05_28_basil_price | v2025_06_30_basil_price | v2025_07_30_basil_price | v2025_08_27_basil_price | v2025_09_30_clover_price | v2025_10_29_clover_price | v2025_11_17_clover_price | v2025_12_15_clover_price | v2026_01_28_clover_price | v2026_02_25_clover_price | v2026_03_25_dahlia_price
    )

    StripeProductPayload: TypeAlias = (
        v2023_08_16_product | v2024_04_03_product | v2023_10_16_product | v2024_04_10_product | v2024_06_20_product | v2024_09_30_acacia_product | v2024_10_28_acacia_product | v2024_11_20_acacia_product | v2024_12_18_acacia_product | v2025_01_27_acacia_product | v2025_02_24_acacia_product | v2025_03_31_basil_product | v2025_04_30_basil_product | v2025_05_28_basil_product | v2025_06_30_basil_product | v2025_07_30_basil_product | v2025_08_27_basil_product | v2025_09_30_clover_product | v2025_10_29_clover_product | v2025_11_17_clover_product | v2025_12_15_clover_product | v2026_01_28_clover_product | v2026_02_25_clover_product | v2026_03_25_dahlia_product
    )

    StripeSubscriptionPayload: TypeAlias = (
        v2023_08_16_subscription | v2024_04_03_subscription | v2023_10_16_subscription | v2024_04_10_subscription | v2024_06_20_subscription | v2024_09_30_acacia_subscription | v2024_10_28_acacia_subscription | v2024_11_20_acacia_subscription | v2024_12_18_acacia_subscription | v2025_01_27_acacia_subscription | v2025_02_24_acacia_subscription | v2025_03_31_basil_subscription | v2025_04_30_basil_subscription | v2025_05_28_basil_subscription | v2025_06_30_basil_subscription | v2025_07_30_basil_subscription | v2025_08_27_basil_subscription | v2025_09_30_clover_subscription | v2025_10_29_clover_subscription | v2025_11_17_clover_subscription | v2025_12_15_clover_subscription | v2026_01_28_clover_subscription | v2026_02_25_clover_subscription | v2026_03_25_dahlia_subscription
    )

    StripeObjectPayload: TypeAlias = (
        StripeChargePayload | StripeCheckoutSessionPayload | StripeCustomerPayload | StripeInvoicePayload | StripePaymentIntentPayload | StripePricePayload | StripeProductPayload | StripeSubscriptionPayload
    )
else:
    class StripeEventPayload(_LazyStripePayloadBase):
        object_type = "event"

    class StripeChargePayload(_LazyStripePayloadBase):
        object_type = "charge"

    class StripeCheckoutSessionPayload(_LazyStripePayloadBase):
        object_type = "checkout.session"

    class StripeCustomerPayload(_LazyStripePayloadBase):
        object_type = "customer"

    class StripeInvoicePayload(_LazyStripePayloadBase):
        object_type = "invoice"

    class StripePaymentIntentPayload(_LazyStripePayloadBase):
        object_type = "payment_intent"

    class StripePricePayload(_LazyStripePayloadBase):
        object_type = "price"

    class StripeProductPayload(_LazyStripePayloadBase):
        object_type = "product"

    class StripeSubscriptionPayload(_LazyStripePayloadBase):
        object_type = "subscription"

    StripeObjectPayload = Any

_ADAPTERS: dict[str, LazyStripeAdapter[Any]] = {
    "event": LazyStripeAdapter("event"),
    "charge": LazyStripeAdapter("charge"),
    "checkout.session": LazyStripeAdapter("checkout.session"),
    "customer": LazyStripeAdapter("customer"),
    "invoice": LazyStripeAdapter("invoice"),
    "payment_intent": LazyStripeAdapter("payment_intent"),
    "price": LazyStripeAdapter("price"),
    "product": LazyStripeAdapter("product"),
    "subscription": LazyStripeAdapter("subscription"),
}

StripeEventAdapter: LazyStripeAdapter[StripeEventPayload] = _ADAPTERS["event"]

StripeChargeAdapter: LazyStripeAdapter[StripeChargePayload] = _ADAPTERS["charge"]

StripeCheckoutSessionAdapter: LazyStripeAdapter[StripeCheckoutSessionPayload] = _ADAPTERS["checkout.session"]

StripeCustomerAdapter: LazyStripeAdapter[StripeCustomerPayload] = _ADAPTERS["customer"]

StripeInvoiceAdapter: LazyStripeAdapter[StripeInvoicePayload] = _ADAPTERS["invoice"]

StripePaymentIntentAdapter: LazyStripeAdapter[StripePaymentIntentPayload] = _ADAPTERS["payment_intent"]

StripePriceAdapter: LazyStripeAdapter[StripePricePayload] = _ADAPTERS["price"]

StripeProductAdapter: LazyStripeAdapter[StripeProductPayload] = _ADAPTERS["product"]

StripeSubscriptionAdapter: LazyStripeAdapter[StripeSubscriptionPayload] = _ADAPTERS["subscription"]

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
