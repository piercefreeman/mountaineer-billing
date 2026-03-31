from enum import StrEnum


class PriceBillingInterval(StrEnum):
    """
    Define the type of interval to charge for this product
    """

    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"
    YEAR = "YEAR"
    ONETIME = "ONETIME"


class StripeStatus(StrEnum):
    ACTIVE = "active"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    PAUSED = "paused"
    CANCELED = "canceled"
    UNPAID = "unpaid"


class StripeWebhookType(StrEnum):
    # https://stripe.com/docs/cli/trigger
    SUBSCRIPTION_CANCELED = "customer.subscription.deleted"
    SUBSCRIPTION_UPDATED = "customer.subscription.updated"
    SUBSCRIPTION_CREATED = "customer.subscription.created"

    CHECKOUT_SESSION_COMPLETE = "checkout.session.completed"


class RollupType(StrEnum):
    # Considers usage over time
    # For instance, a user receives 10 credits in the first month that
    # don't expire in the second month. 10 -> 20 -> etc
    # Users will be given the full credits at the start of the billing cycle
    AGGREGATE = "AGGREGATE"

    # Only tracks usage from the start of the current plan. Usage will reset
    # when the subscription renews. Users will be given the full credits at
    # the start of the billing cycle.
    CURRENT_CYCLE = "CURRENT_CYCLE"
