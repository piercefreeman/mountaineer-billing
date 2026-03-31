from typing import Any, Literal, cast

import stripe
from fastapi import Depends
from iceaxe import DBConnection, select
from iceaxe.mountaineer import DatabaseDependencies

from mountaineer.dependencies import CoreDependencies
from mountaineer_auth import AuthDependencies, UserAuthMixin

from mountaineer_billing import models
from mountaineer_billing.config import BillingConfig
from mountaineer_billing.enums import PriceBillingInterval, StripeStatus
from mountaineer_billing.products import (
    PriceIDBase,
    ProductIDBase,
)

INTERNAL_USER_ID_KEY = "internal_user_id"


async def stripe_customer_id_for_user(
    user: UserAuthMixin = Depends(AuthDependencies.require_valid_user),
    config: BillingConfig = Depends(
        CoreDependencies.get_config_with_type(BillingConfig)
    ),
    db_connection: DBConnection = Depends(DatabaseDependencies.get_db_connection),
) -> str:
    """
    Inspect the current client user session. Determine if they already have a stripe
    Customer object. If not create a new one.

    """
    if not isinstance(user, models.UserBillingMixin):
        raise ValueError(
            f"User model {user} is not a subclass of models.UserBillingMixin"
        )

    if user.stripe_customer_id:
        return user.stripe_customer_id

    # If the user doesn't already have a customer ID assigned, we want to create one
    stripe_customer = stripe.Customer.create(
        name=user.full_name or "Guest Customer",
        email=user.email,
        metadata={
            INTERNAL_USER_ID_KEY: str(user.id),
        },
        api_key=config.STRIPE_API_KEY,
    )

    # Update the user record - it will already live within this session since
    # the dependency injection ensures we use a single common dependency
    # We need to re-fetch the user into the current session, so we can't accept
    # a reference to the user object even if the user has one
    user.stripe_customer_id = stripe_customer.id
    await db_connection.update([user])
    return stripe_customer.id


def customer_session_authorization(
    enabled_components: list[Literal["buy_button", "pricing_table"]],
):
    """
    Create a customer session that is correctly provisioned to be used. Expires
    in 30 minutes. Use like:

    ```python
    async def render(
        self,
        user_billing_authorization: str = Depends(
            BillingDependencies.customer_session_authorization(
                ["pricing_table"]
            )
        )
    ):
        # Pass the user authorization to your pricing table
        ...

    ```

    Supported components are listed at https://docs.stripe.com/api/customer_sessions/create

    """

    def dependency(
        stripe_customer_id: str = Depends(stripe_customer_id_for_user),
        config: BillingConfig = Depends(
            CoreDependencies.get_config_with_type(BillingConfig)
        ),
    ):
        # @pierce 03/01/2024: CustomerSession is not provided in the typeshed definitions for stripe
        customer_session = stripe.CustomerSession.create(  # type: ignore
            customer=stripe_customer_id,
            # Enabled components always follow the same syntax
            components={
                enabled_component: {"enabled": True}
                for enabled_component in enabled_components
            },
            api_key=config.STRIPE_API_KEY,
        )
        return customer_session.client_secret

    return dependency


def checkout_builder(
    db_connection: DBConnection = Depends(DatabaseDependencies.get_db_connection),
    config: BillingConfig = Depends(
        CoreDependencies.get_config_with_type(BillingConfig)
    ),
    stripe_customer_id: str = Depends(stripe_customer_id_for_user),
    user: models.UserBillingMixin = Depends(AuthDependencies.require_valid_user),
):
    """
    Build the URL for a new checkout session, given a list of product objects
    that have been pre-selected by the user.

    These products must either all be ONE_TIME products or all SUBSCRIPTION products.

    """

    async def build_checkout(
        *,
        products: list[tuple[ProductIDBase, PriceIDBase]],
        success_url: str,
        cancel_url: str,
        allow_promotion_codes: bool = False,
    ):
        # Determine what the user is purchasing
        product_price_model = config.BILLING_PRODUCT_PRICE
        stripe_price_ids: list[str] = []

        ids_to_products = {
            (product.id, price.id): (product, price)
            for product in config.BILLING_PRODUCTS
            for price in product.prices
        }

        billing_intervals: set[PriceBillingInterval] = set()

        for product_id, price_id in products:
            if (product_id, price_id) not in ids_to_products:
                raise ValueError(
                    f"Product {product_id} and price {price_id} are not defined in the billing configuration"
                )

            product, price = ids_to_products[(product_id, price_id)]

            product_query = select(product_price_model).where(
                product_price_model.product_id == product.id,
                product_price_model.price_id == price.id,
            )
            product_prices = await db_connection.exec(product_query)
            product_price = product_prices[0] if product_prices else None
            if not product_price:
                raise ValueError(
                    f"Database {price} is not defined for product {product}, make sure the models are synced"
                )

            stripe_price_ids.append(product_price.stripe_price_id)
            billing_intervals.add(price.frequency)

        if PriceBillingInterval.ONETIME in billing_intervals:
            # Stripe constrains checkout sessions to either be "payment" for one-off purchases
            # or "subscription" to manage longer-term billing
            if len(billing_intervals) > 1:
                raise ValueError(
                    "Checkout sessions can only be started for one-time payments, or subscriptions."
                )

        # Create a new checkout for the given user
        metadata = {
            INTERNAL_USER_ID_KEY: str(user.id),
        }
        checkout_mode = (
            "payment"
            if billing_intervals == {PriceBillingInterval.ONETIME}
            else "subscription"
        )
        checkout_kwargs: dict[str, object] = {
            "customer": stripe_customer_id,
            "client_reference_id": str(user.id),
            "line_items": [
                {
                    "price": price_id,
                    "quantity": 1,
                }
                for price_id in stripe_price_ids
            ],
            "mode": checkout_mode,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "allow_promotion_codes": allow_promotion_codes,
            "metadata": metadata,
            "api_key": config.STRIPE_API_KEY,
        }
        if checkout_mode == "payment":
            checkout_kwargs["payment_intent_data"] = {"metadata": metadata}
        else:
            checkout_kwargs["subscription_data"] = {"metadata": metadata}

        checkout_session = cast(Any, stripe.checkout.Session).create(
            **checkout_kwargs,
        )
        return checkout_session.url

    return build_checkout


async def any_subscription(
    config: BillingConfig = Depends(
        CoreDependencies.get_config_with_type(BillingConfig)
    ),
    db_connection: DBConnection = Depends(DatabaseDependencies.get_db_connection),
    user: models.UserBillingMixin = Depends(AuthDependencies.require_valid_user),
) -> models.Subscription | None:
    """
    Returns a "valid" subscription object for the user, if any. This subscription object just
    represents the current state of the user's subscription, and is not necessarily the one
    that is active.

    If the user has *any* subscription in the database (even an expired one), we typically want
    to show them the subscription setting page to allow them to restart an existing subscription
    The exception here are cancelled subscriptions, which can't be reset and are effectively
    discarded from the system.

    https://docs.stripe.com/billing/subscriptions/cancel

    """
    subscription_query = select(config.BILLING_SUBSCRIPTION).where(
        config.BILLING_SUBSCRIPTION.user_id == user.id,
        config.BILLING_SUBSCRIPTION.stripe_status != StripeStatus.CANCELED,
    )
    subscriptions = await db_connection.exec(subscription_query)
    return subscriptions[0] if subscriptions else None


async def edit_checkout_link(
    config: BillingConfig = Depends(
        CoreDependencies.get_config_with_type(BillingConfig)
    ),
    user: models.UserBillingMixin = Depends(AuthDependencies.require_valid_user),
):
    if not user.stripe_customer_id:
        raise ValueError("No stripe_customer_id linked to the current user")

    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        api_key=config.STRIPE_API_KEY,
        # TODO: Implement the return url
        # return_url=request.redirect_url,
    )
    return session.url
