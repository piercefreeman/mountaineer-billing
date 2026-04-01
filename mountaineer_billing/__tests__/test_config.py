from mountaineer_billing.__tests__ import conf_models as models
from mountaineer_billing.config import BillingConfig, BillingModels


def get_common_billing_config_kwargs() -> dict[str, object]:
    return {
        "STRIPE_API_KEY": "",
        "STRIPE_WEBHOOK_SECRET": "",
        "BILLING_PRODUCTS": models.BILLING_PRODUCTS,
        "BILLING_METERED": models.BILLING_METERED,
    }


def test_billing_models_accepts_nested_model_config() -> None:
    config = BillingConfig(
        **get_common_billing_config_kwargs(),
        BILLING_MODELS=BillingModels(
            USER=models.User,
            PRODUCT_PRICE=models.ProductPrice,
            RESOURCE_ACCESS=models.ResourceAccess,
            SUBSCRIPTION=models.Subscription,
            METERED_USAGE=models.MeteredUsage,
            PAYMENT=models.Payment,
            CHECKOUT_SESSION=models.CheckoutSession,
            STRIPE_EVENT=models.StripeEvent,
            STRIPE_OBJECT=models.StripeObject,
            PROJECTION_STATE=models.BillingProjectionState,
        ),
    )

    assert config.BILLING_MODELS.USER is models.User
    assert config.BILLING_MODELS.PRODUCT_PRICE is models.ProductPrice
    assert config.BILLING_USER is models.User
    assert config.BILLING_PRODUCT_PRICE is models.ProductPrice


def test_billing_models_accepts_legacy_flat_model_fields() -> None:
    config = BillingConfig(
        **get_common_billing_config_kwargs(),
        BILLING_USER=models.User,
        BILLING_PRODUCT_PRICE=models.ProductPrice,
        BILLING_RESOURCE_ACCESS=models.ResourceAccess,
        BILLING_SUBSCRIPTION=models.Subscription,
        BILLING_METERED_USAGE=models.MeteredUsage,
        BILLING_PAYMENT=models.Payment,
        BILLING_CHECKOUT_SESSION=models.CheckoutSession,
        BILLING_STRIPE_EVENT=models.StripeEvent,
        BILLING_STRIPE_OBJECT=models.StripeObject,
        BILLING_PROJECTION_STATE=models.BillingProjectionState,
    )

    assert config.BILLING_MODELS.USER is models.User
    assert config.BILLING_MODELS.PRODUCT_PRICE is models.ProductPrice
    assert config.BILLING_MODELS.PROJECTION_STATE is models.BillingProjectionState
