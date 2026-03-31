from __future__ import annotations

from datetime import timedelta

from iceaxe import DBConnection, delete, or_, select
from pydantic import BaseModel
from waymark import Depend, RetryPolicy, Workflow, action, workflow

from mountaineer_billing import models
from mountaineer_billing.config import BillingConfig
from mountaineer_billing.enums import SyncStatus
from mountaineer_billing.logging import LOGGER

from .stripe_sync import (
    checkout_line_items,
    claim_projection_batch,
    finalize_projection_failure,
    finalize_projection_success,
    find_user_for_customer,
    get_billing_config,
    get_db_connection,
    invoice_line_items,
    line_item_price_id,
    line_item_product_id,
    nested_id,
    reschedule_projection,
    safe_stripe_status,
    subscription_items,
    subscription_period_end,
    subscription_period_start,
    sync_user_customer_link,
    to_datetime,
)


class ProjectBillingStateRequest(BaseModel):
    limit: int = 25


class ProjectBillingStateResponse(BaseModel):
    projected_count: int = 0


@workflow
class ProjectStripeBilling(Workflow):
    async def run(  # type: ignore[override]
        self,
        *,
        limit: int = 25,
    ) -> ProjectBillingStateResponse:
        return await self.run_action(
            project_dirty_billing_states(ProjectBillingStateRequest(limit=limit)),
            retry=RetryPolicy(attempts=3, backoff_seconds=5),
            timeout=timedelta(seconds=60),
        )


@action
async def project_dirty_billing_states(
    request: ProjectBillingStateRequest,
    config: BillingConfig = Depend(get_billing_config),  # type: ignore[assignment]
    db_connection: DBConnection = Depend(get_db_connection),  # type: ignore[assignment]
) -> ProjectBillingStateResponse:
    claimed_rows = await claim_projection_batch(
        limit=request.limit,
        db_connection=db_connection,
        config=config,
    )

    projected_count = 0
    for projection_state in claimed_rows:
        try:
            pending_query = (
                select(config.BILLING_STRIPE_OBJECT.id)
                .where(
                    config.BILLING_STRIPE_OBJECT.stripe_customer_id
                    == projection_state.stripe_customer_id
                )
                .where(
                    or_(
                        config.BILLING_STRIPE_OBJECT.sync_status
                        == SyncStatus.PENDING,
                        config.BILLING_STRIPE_OBJECT.sync_status
                        == SyncStatus.SYNCING,
                    )
                )
                .limit(1)
            )
            pending_objects = await db_connection.exec(pending_query)
            if pending_objects:
                await reschedule_projection(
                    projection_state=projection_state,
                    delay_seconds=5,
                    config=config,
                    db_connection=db_connection,
                )
                continue

            user = await find_user_for_customer(
                stripe_customer_id=projection_state.stripe_customer_id,
                internal_user_id=projection_state.internal_user_id,
                config=config,
                db_connection=db_connection,
            )
            if not user:
                raise ValueError(
                    "Could not find local user for stripe customer "
                    f"{projection_state.stripe_customer_id}"
                )

            await sync_user_customer_link(
                user=user,
                stripe_customer_id=projection_state.stripe_customer_id,
                db_connection=db_connection,
            )

            stripe_objects_query = select(config.BILLING_STRIPE_OBJECT).where(
                config.BILLING_STRIPE_OBJECT.stripe_customer_id
                == projection_state.stripe_customer_id,
                config.BILLING_STRIPE_OBJECT.sync_status == SyncStatus.CLEAN,
            )
            stripe_objects = await db_connection.exec(stripe_objects_query)

            product_price_query = select(config.BILLING_PRODUCT_PRICE)
            product_prices = await db_connection.exec(product_price_query)
            product_prices_by_stripe_id = {
                product_price.stripe_price_id: product_price
                for product_price in product_prices
            }

            subscriptions_payload = [
                stripe_object.payload
                for stripe_object in stripe_objects
                if stripe_object.object_type == "subscription"
            ]
            invoices_payload = [
                stripe_object.payload
                for stripe_object in stripe_objects
                if stripe_object.object_type == "invoice"
            ]
            checkout_sessions_payload = [
                stripe_object.payload
                for stripe_object in stripe_objects
                if stripe_object.object_type == "checkout.session"
            ]

            subscription_rows: list[models.Subscription] = []
            resource_rows: list[models.ResourceAccess] = []
            payment_rows: list[models.Payment] = []
            checkout_session_rows: list[models.CheckoutSession] = []

            checkout_session_by_subscription: dict[str, str] = {}
            for payload in checkout_sessions_payload:
                checkout_session_id = payload.get("id")
                if not isinstance(checkout_session_id, str):
                    continue

                stripe_subscription_id = nested_id(payload.get("subscription"))
                checkout_session_row = config.BILLING_CHECKOUT_SESSION(
                    stripe_checkout_session_id=checkout_session_id,
                    stripe_payment_intent_id=nested_id(payload.get("payment_intent")),
                    stripe_subscription_id=stripe_subscription_id,
                    stripe_customer_id=projection_state.stripe_customer_id,
                    user_id=user.id,
                )
                checkout_session_rows.append(checkout_session_row)
                if stripe_subscription_id:
                    checkout_session_by_subscription[stripe_subscription_id] = (
                        checkout_session_id
                    )

            for payload in subscriptions_payload:
                stripe_subscription_id = payload.get("id")
                if not isinstance(stripe_subscription_id, str):
                    continue

                subscription_row = config.BILLING_SUBSCRIPTION(
                    stripe_subscription_id=stripe_subscription_id,
                    stripe_status=safe_stripe_status(payload.get("status")),
                    stripe_current_period_start=subscription_period_start(payload),
                    stripe_current_period_end=subscription_period_end(payload),
                    stripe_checkout_session_id=checkout_session_by_subscription.get(
                        stripe_subscription_id
                    ),
                    user_id=user.id,
                )
                subscription_rows.append(subscription_row)

                ended_at = to_datetime(payload.get("ended_at"))
                for item in subscription_items(payload):
                    price_id = line_item_price_id(item)
                    if not price_id:
                        continue

                    local_price = product_prices_by_stripe_id.get(price_id)
                    if not local_price:
                        raise ValueError(
                            f"Local plan not found for stripe price {price_id}"
                        )

                    quantity = item.get("quantity")
                    resource_rows.append(
                        config.BILLING_RESOURCE_ACCESS(
                            started_datetime=to_datetime(item.get("current_period_start"))
                            or subscription_period_start(payload),
                            ended_datetime=ended_at,
                            stripe_subscription_id=stripe_subscription_id,
                            stripe_price_id=price_id,
                            stripe_product_id=line_item_product_id(item),
                            product_id=local_price.product_id,
                            prorated_usage=float(quantity or 1),
                            user_id=user.id,
                        )
                    )

            seen_payment_keys: set[tuple[str, str, str | None]] = set()
            for payload in invoices_payload:
                if not payload.get("paid"):
                    continue

                stripe_invoice_id = payload.get("id")
                if not isinstance(stripe_invoice_id, str):
                    continue

                stripe_subscription_id = nested_id(payload.get("subscription"))
                for line_item in invoice_line_items(payload):
                    price_id = line_item_price_id(line_item)
                    if not price_id:
                        continue

                    payment_key = ("invoice", stripe_invoice_id, price_id)
                    if payment_key in seen_payment_keys:
                        continue
                    seen_payment_keys.add(payment_key)

                    price_value = line_item.get("price")
                    unit_amount = None
                    if isinstance(price_value, dict):
                        raw_unit_amount = price_value.get("unit_amount")
                        if isinstance(raw_unit_amount, int):
                            unit_amount = raw_unit_amount

                    quantity = line_item.get("quantity")
                    if not isinstance(quantity, int) or quantity == 0:
                        quantity = 1

                    paid_amount = line_item.get("amount")
                    if not isinstance(paid_amount, int):
                        paid_amount = payload.get("amount_paid")
                    if not isinstance(paid_amount, int):
                        continue

                    total_price_amount = (
                        unit_amount * quantity if unit_amount else paid_amount
                    )
                    payment_rows.append(
                        config.BILLING_PAYMENT(
                            paid_amount=paid_amount,
                            total_price_amount=total_price_amount,
                            price_ratio=(
                                paid_amount / total_price_amount
                                if total_price_amount
                                else 1.0
                            ),
                            stripe_subscription_id=stripe_subscription_id,
                            stripe_customer_id=projection_state.stripe_customer_id,
                            stripe_price_id=price_id,
                            stripe_invoice_id=stripe_invoice_id,
                            user_id=user.id,
                        )
                    )

            for payload in checkout_sessions_payload:
                if payload.get("payment_status") != "paid":
                    continue
                if nested_id(payload.get("subscription")):
                    continue

                stripe_checkout_session_id = payload.get("id")
                if not isinstance(stripe_checkout_session_id, str):
                    continue

                stripe_invoice_id = nested_id(payload.get("invoice"))
                for line_item in checkout_line_items(payload):
                    price_id = line_item_price_id(line_item)
                    if not price_id:
                        continue

                    local_price = product_prices_by_stripe_id.get(price_id)
                    if not local_price:
                        raise ValueError(
                            f"Local plan not found for stripe price {price_id}"
                        )

                    payment_key = ("checkout", stripe_checkout_session_id, price_id)
                    if payment_key not in seen_payment_keys:
                        seen_payment_keys.add(payment_key)

                        price_value = line_item.get("price")
                        unit_amount = None
                        if isinstance(price_value, dict):
                            raw_unit_amount = price_value.get("unit_amount")
                            if isinstance(raw_unit_amount, int):
                                unit_amount = raw_unit_amount

                        quantity = line_item.get("quantity")
                        if not isinstance(quantity, int) or quantity == 0:
                            quantity = 1

                        paid_amount = line_item.get("amount_subtotal")
                        if not isinstance(paid_amount, int):
                            paid_amount = (
                                unit_amount * quantity if unit_amount else None
                            )
                        if isinstance(paid_amount, int):
                            total_price_amount = (
                                unit_amount * quantity if unit_amount else paid_amount
                            )
                            payment_rows.append(
                                config.BILLING_PAYMENT(
                                    paid_amount=paid_amount,
                                    total_price_amount=total_price_amount,
                                    price_ratio=(
                                        paid_amount / total_price_amount
                                        if total_price_amount
                                        else 1.0
                                    ),
                                    stripe_subscription_id=None,
                                    stripe_customer_id=projection_state.stripe_customer_id,
                                    stripe_price_id=price_id,
                                    stripe_invoice_id=stripe_invoice_id,
                                    user_id=user.id,
                                )
                            )

                    quantity = line_item.get("quantity")
                    resource_rows.append(
                        config.BILLING_RESOURCE_ACCESS(
                            started_datetime=to_datetime(payload.get("created")),
                            stripe_subscription_id=None,
                            is_perpetual=True,
                            prorated_usage=float(quantity or 1),
                            stripe_price_id=price_id,
                            stripe_product_id=line_item_product_id(line_item),
                            product_id=local_price.product_id,
                            user_id=user.id,
                        )
                    )

            async with db_connection.transaction():
                await db_connection.exec(
                    delete(config.BILLING_RESOURCE_ACCESS).where(
                        config.BILLING_RESOURCE_ACCESS.user_id == user.id
                    )
                )
                await db_connection.exec(
                    delete(config.BILLING_SUBSCRIPTION).where(
                        config.BILLING_SUBSCRIPTION.user_id == user.id
                    )
                )
                await db_connection.exec(
                    delete(config.BILLING_PAYMENT).where(
                        config.BILLING_PAYMENT.user_id == user.id
                    )
                )
                await db_connection.exec(
                    delete(config.BILLING_CHECKOUT_SESSION).where(
                        config.BILLING_CHECKOUT_SESSION.user_id == user.id
                    )
                )

                await db_connection.insert(checkout_session_rows)
                await db_connection.insert(subscription_rows)
                await db_connection.insert(resource_rows)
                await db_connection.insert(payment_rows)

            await finalize_projection_success(
                projection_state=projection_state,
                config=config,
                db_connection=db_connection,
            )
            projected_count += 1
        except Exception as exc:
            LOGGER.exception(
                "Failed to project billing state for customer %s",
                projection_state.stripe_customer_id,
            )
            await finalize_projection_failure(
                projection_state=projection_state,
                error=exc,
                config=config,
                db_connection=db_connection,
            )

    return ProjectBillingStateResponse(projected_count=projected_count)
