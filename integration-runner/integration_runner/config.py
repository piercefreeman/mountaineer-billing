from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from iceaxe.mountaineer import DatabaseConfig
from pydantic import Field, model_validator

from mountaineer import ConfigBase
from mountaineer.config import get_config
from mountaineer_auth import AuthConfig

from integration_runner import models
from mountaineer_billing.config import BillingConfig, BillingModels
from mountaineer_billing.products import MeteredDefinition, MeteredIDBase, ProductBase


class IntegrationRunnerConfig(ConfigBase, AuthConfig, BillingConfig, DatabaseConfig):
    PACKAGE: str = "integration_runner"

    POSTGRES_HOST: str = "localhost"
    POSTGRES_USER: str = "mountaineer_billing"
    POSTGRES_PASSWORD: str = "mysecretpassword"
    POSTGRES_DB: str = "mountaineer_billing_test_db"
    POSTGRES_PORT: int = 5436

    API_SECRET_KEY: str = "integration-runner-dev-secret"
    STRIPE_WEBHOOK_SECRET: str = "whsec_integration_runner_unused"

    AUTH_USER: type[models.User] = models.User
    AUTH_VERIFICATION_STATE: type[models.VerificationState] = models.VerificationState

    BILLING_MODELS: BillingModels = BillingModels(
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
    )
    BILLING_PRODUCTS: Sequence[ProductBase] = models.BILLING_PRODUCTS
    BILLING_METERED: Mapping[MeteredIDBase, MeteredDefinition] = models.BILLING_METERED

    INTEGRATION_RUNNER_USER_EMAIL: str = "checkout-runner@example.com"
    INTEGRATION_RUNNER_USER_PASSWORD: str = "integration-runner-password"
    INTEGRATION_RUNNER_FULL_NAME: str = "Integration Runner"
    INTEGRATION_RUNNER_PRODUCT_ID: models.ProductID = models.ProductID.ONEOFF_50_ITEMS
    INTEGRATION_RUNNER_PRICE_ID: models.PriceID = models.PriceID.DEFAULT
    INTEGRATION_RUNNER_SUCCESS_URL: str = "https://example.com/billing/success"
    INTEGRATION_RUNNER_CANCEL_URL: str = "https://example.com/billing/cancel"
    INTEGRATION_RUNNER_ALLOW_PROMOTION_CODES: bool = False
    INTEGRATION_RUNNER_CARD_NUMBER: str = "4242424242424242"
    INTEGRATION_RUNNER_CARD_EXPIRY: str = "1234"
    INTEGRATION_RUNNER_CARD_CVC: str = "123"
    INTEGRATION_RUNNER_CARDHOLDER_NAME: str = "Integration Runner"
    INTEGRATION_RUNNER_POSTAL_CODE: str = "94107"
    INTEGRATION_RUNNER_VIDEO_DIR: Path = Field(
        default=Path("artifacts/integration-runner/videos")
    )
    INTEGRATION_RUNNER_SLOW_MO_MS: int = 250
    INTEGRATION_RUNNER_TIMEOUT_MS: int = 5_000
    INTEGRATION_RUNNER_PAUSE_AFTER_MS: int = 5_000
    INTEGRATION_RUNNER_SUBMIT: bool = False

    @model_validator(mode="after")
    def validate_test_stripe_key(self) -> "IntegrationRunnerConfig":
        if not self.STRIPE_API_KEY.startswith("sk_test_"):
            raise ValueError(
                "IntegrationRunnerConfig requires STRIPE_API_KEY to start with 'sk_test_'."
            )

        return self


def get_runner_config() -> IntegrationRunnerConfig:
    try:
        config = get_config()
    except ValueError:
        return IntegrationRunnerConfig()

    if not isinstance(config, IntegrationRunnerConfig):
        raise ValueError(
            "The active Mountaineer config is not an IntegrationRunnerConfig instance."
        )

    return config
