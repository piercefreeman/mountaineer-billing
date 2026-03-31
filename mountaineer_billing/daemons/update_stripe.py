from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import asyncpg
import stripe
from iceaxe import DBConnection, select
from iceaxe.mountaineer import DatabaseConfig
from pydantic import BaseModel
from waymark import Depend, RetryPolicy, Workflow, action, workflow

from mountaineer.dependencies import CoreDependencies

from mountaineer_billing import models
from mountaineer_billing.config import BillingConfig
from mountaineer_billing.enums import StripeStatus, StripeWebhookType
from mountaineer_billing.logging import LOGGER


class UpdateStripeRequest(BaseModel):
    type: StripeWebhookType
    payload: dict[str, Any]


class UpdateStripeResponse(BaseModel):
    pass


def get_billing_config() -> BillingConfig:
    """Dependency provider for BillingConfig."""
    return CoreDependencies.get_config_with_type(BillingConfig)()


def get_database_config() -> DatabaseConfig:
    """Dependency provider for DatabaseConfig."""
    return CoreDependencies.get_config_with_type(DatabaseConfig)()


async def get_db_connection():
    """Dependency provider for database connection."""
    config = get_database_config()
    conn = await asyncpg.connect(
        host=config.POSTGRES_HOST,
        port=config.POSTGRES_PORT,
        user=config.POSTGRES_USER,
        password=config.POSTGRES_PASSWORD,
        database=config.POSTGRES_DB,
    )
    try:
        yield DBConnection(conn)
    finally:
        await conn.close()


@workflow
class UpdateStripe(Workflow):
    """
    Handle an incoming Stripe webhook and updates our local purchase state.

    """

    async def run(  # type: ignore[override]
        self,
        *args,
        type: str,
        payload: dict[str, Any],
        **kwargs,
    ) -> None:
        if (
            type == StripeWebhookType.SUBSCRIPTION_CANCELED.value
            or type == StripeWebhookType.SUBSCRIPTION_UPDATED.value
        ):
            await self.run_action(
                update_subscription(UpdateSubscriptionRequest(payload=payload)),
                retry=RetryPolicy(attempts=3, backoff_seconds=5),
                timeout=timedelta(seconds=30),
            )
        elif type == StripeWebhookType.SUBSCRIPTION_CREATED.value:
            await self.run_action(
                create_subscription(CreateSubscriptionRequest(payload=payload)),
                retry=RetryPolicy(attempts=3, backoff_seconds=5),
                timeout=timedelta(seconds=30),
            )
        elif type == StripeWebhookType.CHECKOUT_SESSION_COMPLETE.value:
            await self.run_action(
                complete_checkout_session(
                    CompleteCheckoutSessionRequest(payload=payload)
                ),
                retry=RetryPolicy(attempts=3, backoff_seconds=5),
                timeout=timedelta(seconds=30),
            )


class UpdateSubscriptionRequest(BaseModel):
    payload: dict[str, Any]


@action
async def update_subscription(
    request: UpdateSubscriptionRequest,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(get_db_connection),  # type: ignore[assignment]
) -> None:
    stripe_subscription = stripe.Subscription.construct_from(
        request.payload["data"]["object"], config.STRIPE_API_KEY
    )

    async with db_connection.transaction():
        subscription_query = select(config.BILLING_SUBSCRIPTION).where(
            config.BILLING_SUBSCRIPTION.stripe_subscription_id == stripe_subscription.id
        )
        subscriptions = await db_connection.exec(subscription_query)
        subscription = subscriptions[0] if subscriptions else None

        if not subscription:
            raise ValueError(f"Subscription {stripe_subscription.id} not found")

        # For now we can assume that the subscription will only have one item
        subscription_item = stripe_subscription["items"].data[0]

        subscription.stripe_status = StripeStatus(stripe_subscription.status)
        subscription.stripe_current_period_start = datetime.fromtimestamp(
            subscription_item.current_period_start, timezone.utc
        )
        subscription.stripe_current_period_end = datetime.fromtimestamp(
            subscription_item.current_period_end, timezone.utc
        )
        await db_connection.update([subscription])

        # NOTE - we can potentially migrate this to use billing_cycle_anchor
        if subscription_item.current_period_start:
            # Modify the access grants to reflect the new period - this typically
            # happens in the case of a trial converting to a paid subscription; we
            # should start their normal billing cycle from the current period start
            access_grant_query = select(config.BILLING_RESOURCE_ACCESS).where(
                config.BILLING_RESOURCE_ACCESS.subscription_id == subscription.id
            )
            access_grants = await db_connection.exec(access_grant_query)
            for access_grant in access_grants:
                access_grant.started_datetime = datetime.fromtimestamp(
                    subscription_item.current_period_start, timezone.utc
                )
            await db_connection.update(access_grants)

        if stripe_subscription.ended_at:
            # Remove all access grants that are linked to this subscription
            access_grant_query = select(config.BILLING_RESOURCE_ACCESS).where(
                config.BILLING_RESOURCE_ACCESS.subscription_id == subscription.id
            )
            access_grants = await db_connection.exec(access_grant_query)
            for access_grant in access_grants:
                access_grant.ended_datetime = datetime.fromtimestamp(
                    stripe_subscription.ended_at, timezone.utc
                )
            await db_connection.update(access_grants)

        if subscription_item.plan:
            # Try to find what price the remote object maps to
            price_query = select(config.BILLING_PRODUCT_PRICE).where(
                config.BILLING_PRODUCT_PRICE.stripe_price_id
                == subscription_item.plan.id
            )
            prices = await db_connection.exec(price_query)
            price = prices[0] if prices else None

            if price:
                access_grant_query = select(config.BILLING_RESOURCE_ACCESS).where(
                    config.BILLING_RESOURCE_ACCESS.subscription_id == subscription.id
                )
                access_grants = await db_connection.exec(access_grant_query)

                # We only expect one but we update all
                for access_grant in access_grants:
                    access_grant.product_id = price.product_id
                await db_connection.update(access_grants)
            else:
                raise ValueError(
                    f"Price {subscription_item.plan.id} not found for subscription {stripe_subscription.id}"
                )


class CreateSubscriptionRequest(BaseModel):
    payload: dict[str, Any]


@action
async def create_subscription(
    request: CreateSubscriptionRequest,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(get_db_connection),  # type: ignore[assignment]
) -> None:
    stripe_subscription = stripe.Subscription.construct_from(
        request.payload["data"]["object"], config.STRIPE_API_KEY
    )

    # Find the customer from this subscription
    async with db_connection.transaction():
        user_query = select(config.BILLING_USER).where(
            config.BILLING_USER.stripe_customer_id == stripe_subscription.customer
        )
        users = await db_connection.exec(user_query)
        user = users[0] if users else None
        if not user:
            raise ValueError(
                f"Local user reference not found for customer {stripe_subscription.customer} in subscription {stripe_subscription.id}"
            )

        # For now we can assume that the subscription will only have one item
        subscription_item = stripe_subscription["items"].data[0]

        subscription_obj = config.BILLING_SUBSCRIPTION(
            stripe_subscription_id=stripe_subscription.id,
            stripe_status=StripeStatus(stripe_subscription.status),
            stripe_current_period_start=datetime.fromtimestamp(
                subscription_item.current_period_start, timezone.utc
            ),
            stripe_current_period_end=datetime.fromtimestamp(
                subscription_item.current_period_end, timezone.utc
            ),
            user_id=user.id,
        )
        await db_connection.insert([subscription_obj])

        # Get all the local plans
        plans_query = select(config.BILLING_PRODUCT_PRICE)
        plans = await db_connection.exec(plans_query)
        local_plans = {plan.stripe_price_id: plan for plan in plans}

        # For each item in the subscription, we want to grant the user access to the
        # given plan
        resources: list[models.ResourceAccess] = []
        for subscription_item in stripe_subscription["items"]:
            if subscription_item.price.id not in local_plans:
                raise ValueError(
                    f"Local plan not found for stripe price {subscription_item.price.id}"
                )

            # Grant the user access to these resources that are linked to this session
            resource = config.BILLING_RESOURCE_ACCESS(
                started_datetime=datetime.fromtimestamp(
                    subscription_item.current_period_start, timezone.utc
                ),
                subscription_id=subscription_obj.id,
                stripe_price_id=subscription_item.price.id,
                stripe_product_id=subscription_item.price.product,
                product_id=local_plans[subscription_item.price.id].product_id,
                user_id=user.id,
            )
            resources.append(resource)

        await db_connection.insert(resources)


class CompleteCheckoutSessionRequest(BaseModel):
    payload: dict[str, Any]


class CompleteCheckoutSessionResponse(BaseModel):
    checkout_session_id: UUID
    payment_ids: list[UUID]


@action
async def complete_checkout_session(
    request: CompleteCheckoutSessionRequest,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(get_db_connection),  # type: ignore[assignment]
) -> CompleteCheckoutSessionResponse:
    checkout_session = stripe.checkout.Session.construct_from(
        request.payload["data"]["object"], config.STRIPE_API_KEY
    )

    async with db_connection.transaction():
        user_query = select(config.BILLING_USER).where(
            config.BILLING_USER.stripe_customer_id == checkout_session.customer
        )
        users = await db_connection.exec(user_query)
        user = users[0] if users else None
        if not user:
            raise ValueError(f"User {checkout_session.customer} not found")

        # Get all the local plans
        plans_query = select(config.BILLING_PRODUCT_PRICE)
        plans = await db_connection.exec(plans_query)
        local_plans = {plan.stripe_price_id: plan for plan in plans}

        payment_items: list[models.Payment] = []
        if checkout_session.payment_status == "paid":
            line_items = stripe.checkout.Session.list_line_items(  # type: ignore
                checkout_session.id,
                api_key=config.STRIPE_API_KEY,
            )

            for line_item in line_items:
                if not (
                    line_item.price
                    and line_item.price.unit_amount
                    and line_item.quantity
                ):
                    LOGGER.warning(f"Line item {line_item.id} has no price")
                    continue

                # amount_total includes tax
                paid_amount = line_item.amount_subtotal
                total_price_amount = line_item.price.unit_amount * line_item.quantity

                payment_obj = config.BILLING_PAYMENT(
                    paid_amount=paid_amount,
                    total_price_amount=total_price_amount,
                    price_ratio=paid_amount / total_price_amount,
                    stripe_subscription_id=checkout_session.subscription,
                    stripe_customer_id=checkout_session.customer,
                    stripe_price_id=line_item.price.id,
                    stripe_invoice_id=checkout_session.invoice,
                    user_id=user.id,
                )
                await db_connection.insert([payment_obj])
                payment_items.append(payment_obj)

                # If this object isn't a subscription, it's a one-off object
                # that should grant access permissions accordingly
                if not checkout_session.subscription:
                    resource = config.BILLING_RESOURCE_ACCESS(
                        started_datetime=datetime.fromtimestamp(
                            checkout_session.created, timezone.utc
                        ),
                        stripe_price_id=line_item.price.id,
                        stripe_product_id=line_item.price.product,
                        product_id=local_plans[line_item.price.id].product_id,
                        is_perpetual=True,
                        subscription_id=None,
                        user_id=user.id,
                    )
                    await db_connection.insert([resource])

        checkout_session_obj = config.BILLING_CHECKOUT_SESSION(
            stripe_payment_intent_id=checkout_session.payment_intent,
            stripe_subscription_id=checkout_session.subscription,
            stripe_customer_id=checkout_session.customer,
            user_id=user.id,
        )
        await db_connection.insert([checkout_session_obj])

        # If the checkout session is now linked to a subscription, update the subscription's
        # back reference to this checkout session
        if checkout_session.subscription:
            subscription_query = select(config.BILLING_SUBSCRIPTION).where(
                config.BILLING_SUBSCRIPTION.stripe_subscription_id
                == checkout_session.subscription
            )
            subscriptions = await db_connection.exec(subscription_query)
            if subscriptions:
                for subscription in subscriptions:
                    subscription.checkout_session_id = checkout_session_obj.id
                await db_connection.update(subscriptions)

        return CompleteCheckoutSessionResponse(
            checkout_session_id=checkout_session_obj.id,
            payment_ids=[payment.id for payment in payment_items],
        )
