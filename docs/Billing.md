# Billing

Software billing seems simple on the surface, but once you dive into the different cases.

Terms:

Entitlement: A user's right to access a product or service. This might be faciliated through a subscription or a one-time purchase. The entitlement might have a quantity (like limited bandwidth per month).

Meter: When entitlements are limited (ie. 10 items a month, or 20 credits for all-time) they're defined as metered resources. We track the usage of these resources in order to figure out if a user has additional granted capacity. We often use "metered resources" and "credits" interchangeably.

Allocation: The overall amount of credits that the user has access to at this given time. Allocations represent the full, un-debited amount of credits.

Usage: The amount of credits that the user has at the given point in time.

## Metering / Account Debit

- We will debit from subscription plans before we debit from one-off purchases, with the idea that users expect to use their monthly allocation before they fallback on the additional capacity provided by a oneoff purchase.
