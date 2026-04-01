# Billing

Most teams meet billing at the moment they stop asking "can we monetize this?"
and start asking "what will the user actually feel when they hit a paywall or a
quota?". `mountaineer-billing` is opinionated about that second question.

Stripe is still the payment processor, but the repo's main abstractions are
closer to the way SaaS users think:

- "I'm on Pro"
- "This plan renews every month"
- "I get 20 generations included"
- "I bought extra credits when I ran out"
- "Can I still do this action right now?"

That is the right mental starting point if you have not monetized a project
before. Users do not think in terms of checkout sessions, invoice line items, or
subscription item payloads. They think in terms of access, limits, renewals, and
top-ups.

At runtime, almost every billing question in this repo collapses to two checks:

1. Does this user currently have access to this thing?
2. Does this user still have enough remaining capacity to perform this action?

Everything else exists to keep those two answers correct.

## The User-Facing Mental Model

A user usually experiences billing in a sequence that looks like this:

1. They choose a plan or buy a one-time pack.
2. That purchase unlocks some access.
3. That access may include quota for one or more metered resources.
4. Their actions consume that quota over time.
5. A renewal may refresh some quota, while one-time credits continue to sit in
   reserve until they are used.

This repo tries to mirror that experience directly.

Instead of making the application reason about Stripe's full object graph, it
projects billing into simpler local tables and dependencies:

- `Subscription` answers "what recurring billing state does this user have?"
- `ResourceAccess` answers "what did they buy, and is it still active?"
- `Payment` answers "what have they paid for?"
- `MeteredUsage` answers "how much of a metered resource have they consumed?"

That is a better semantic map for product code than "find the right nested field
inside a webhook payload and hope Stripe did not rename it in a later API
version".

## The Three Layers

It helps to think of the billing system as three layers.

### 1. Catalog Defined In Code

Your application defines the billing catalog locally in `BILLING_PRODUCTS` and
`BILLING_METERED`.

This is an important design choice in the repo. Stripe is not the authoring
surface for your product model. Your code is.

That means you define stable internal ids for:

- products, such as `PRO` or `CREDIT_PACK`
- prices, such as `DEFAULT` or regional variants
- metered resources, such as `ITEM_GENERATION`

Those internal ids are what the rest of your app should care about. Stripe ids
like `price_...` and `prod_...` are treated more like deployment details and are
mapped through `ProductPrice`.

The sync CLI closes the loop on that model:

- `billing-sync up` pushes the local catalog into Stripe and stores price
  mappings locally
- `billing-sync down` mirrors supported Stripe objects back into the local raw
  billing state
- `stripe-sync materialize` rebuilds local billing projections for users that
  already have a Stripe customer id

### 2. Raw Stripe Mirror

Stripe webhooks are first persisted as immutable `StripeEvent` rows. From there,
the repo rebuilds a canonical local snapshot of supported Stripe objects in
`StripeObject`.

This gives the system an audit trail and a stable recovery path:

- the saved event is the historical record of what Stripe told us
- the mirrored object is the latest known state of that Stripe object
- typed Stripe payloads isolate most Stripe-version churn from the rest of the
  app

### 3. App-Facing Projections

The application is expected to read the derived tables, not the raw Stripe
mirror.

`BillingProjectionState` tracks whether a customer's billing projections need to
be rebuilt. The projection workflow then materializes the customer's current
billing state into `CheckoutSession`, `Subscription`, `ResourceAccess`, and
`Payment`.

This is another core idea in the repo: purchased state is rebuildable from the
Stripe mirror, but usage is not. `MeteredUsage` is a local ledger of what the
user has already consumed. If you lose Stripe data, you can sync it back down.
If you lose your local usage ledger, Stripe cannot reconstruct it for you.

## Core Concepts

### Product

A product is the thing the user believes they are buying.

In this repo there are two catalog shapes:

- `LicensedProduct`: the user buys access or quota up front
- `MeteredProduct`: the user is billed according to usage over time

Most of the quota and entitlement helpers in the current runtime are centered on
`LicensedProduct`, because that is the common shape for "plan plus included
credits" and "one-time credit pack" experiences.

### Price

A price describes how money is collected for a product.

The same product can have different prices for different intervals or regions.
A price may be:

- recurring, such as monthly or yearly
- one-time, such as a top-up or credit pack

This distinction matters because it changes the shape of the user's experience.
A monthly plan feels like ongoing access. A one-time purchase feels like reserve
capacity.

### Meter

A meter is a named resource that you count.

Examples:

- number of items generated
- number of documents processed
- amount of bandwidth consumed

Meters are intentionally closer to product language than to payment language.
Users understand "I have 20 generations left" much faster than they understand
"my invoice contains a metered line item".

### Entitlement

An entitlement is what a product grants.

In practice, that usually means one of two things:

- binary access to a capability
- a quantity of some metered resource

For licensed products in this repo, entitlements are commonly expressed as
`CountDownMeteredAllocation`s. A plan may grant 20 generations. A credit pack
may grant 50 generations. They are both entitlements, even though one renews and
the other does not.

### Resource Access

`ResourceAccess` is the repo's most important bridge between purchases and
runtime behavior.

It means: "this user currently has access to this product". The row also carries
the time window of that access and whether it should be treated as perpetual.

That lets the repo express several common user experiences in one model:

- an active subscription that is still granting access
- a canceled subscription whose access has ended
- a one-time purchase that should continue to exist as a permanent reserve

### Allocation

Allocation is the amount of capacity the user should be treated as having right
now.

It is not stored as a single master number. Instead, the repo computes it from
the user's active `ResourceAccess` rows and the entitlements defined on the local
product catalog.

This is why the system feels closer to product semantics than payment semantics:
the question is not "what invoices exist?", but "given everything this user has
bought, what should they currently be allowed to do?".

### Usage

Usage is how much of a metered resource the user has already consumed.

In this repo, that is stored in `MeteredUsage`. This is a debit ledger, not a
catalog definition and not a Stripe mirror. It is the local record of product
actions that have already happened.

### Rollup

`RollupType` defines how usage should be interpreted:

- `CURRENT_CYCLE` means usage resets with the current billing cycle
- `AGGREGATE` means usage is counted across all time

This maps well to how users think:

- monthly included quota usually feels like "it resets"
- a one-time credit pack usually feels like "it stays until I use it"

## Renewable Quota vs Reserve Credits

One of the more useful concepts in this repo is the split between variable and
perpetual capacity.

- Variable capacity is quota that effectively refreshes with a billing cycle.
  Subscription plans usually feel like this.
- Perpetual capacity is quota that does not reset. One-time top-ups and credit
  packs usually feel like this.

The dependency layer reflects that distinction through `CapacityAllocation`.

This produces a user-facing behavior that usually feels right: when usage is
recorded, the system debits subscription quota before it debits one-time reserve
credits. In other words, the monthly allowance gets used first, and the
permanent top-up only starts shrinking after the renewable quota is exhausted.

That is not just an implementation detail. It is a product decision encoded in
the billing model:

- users expect their included monthly quota to be consumed first
- users expect paid top-ups to act like overflow protection, not to disappear
  while their plan quota is still sitting unused

## Why The App Reads Projections Instead Of Stripe

Stripe's object model is rich, but it is not the easiest model to build product
logic on top of.

The repo therefore uses a projection flow:

1. receive a webhook
2. persist the validated event in `StripeEvent`
3. upsert the latest Stripe object snapshot into `StripeObject`
4. trigger projection work for the relevant customer
5. rebuild `CheckoutSession`, `Subscription`, `ResourceAccess`, and `Payment`

This keeps the application side simple. Account pages, feature gates, and quota
checks can read local tables with stable meanings instead of repeatedly
re-deriving billing state from raw Stripe payloads.

It also gives you a clean operational story:

- sync catalog definitions up to Stripe
- sync Stripe objects back down if needed
- replay saved events when reconciling
- rebuild customer projections from the raw mirror

## A Concrete Example

Imagine a user starts with no billing history at all.

At first, there is no Stripe customer, no access rows, and no usage story to
care about. The app is effectively still in its pre-monetization state.

Then the user buys a monthly Pro plan:

- the plan is represented locally as a `LicensedProduct`
- the monthly charge is represented by a `Price`
- the plan grants an entitlement like "20 item generations"
- after checkout and webhook processing, the user gets `ResourceAccess`
- `verify_capacity(...)` can now answer whether they still have room to perform
  another generation

Later, the same user buys a one-time 50-credit pack:

- they get another `ResourceAccess` row
- this one is marked as perpetual
- their effective allocation now includes both renewable plan quota and reserve
  credits

As they consume usage:

- `record_metered_usage(...)` writes to `MeteredUsage`
- monthly quota is debited before the reserve pack
- when the next billing cycle arrives, the renewable portion effectively resets
  according to the meter's rollup rules, while the one-time pack remains

That is a much closer match to how users talk about billing than a direct Stripe
object diagram would be.

## If You Are Monetizing For The First Time

The safest way to introduce billing is to start with a very small vocabulary.

Define:

- one or two `LicensedProduct`s
- one `MeteredID` for the expensive action you actually care about
- a recurring plan if you want included usage
- a one-time pack if you want overflow capacity

Then wire the product behavior where users will actually feel it:

- use `checkout_builder(...)` to start purchases
- use `verify_capacity(...)` before expensive actions
- use `record_metered_usage(...)` when the action succeeds
- use `Subscription`, `ResourceAccess`, and `Payment` to build account pages

If you keep the user-facing story clear, the technical model in this repo lines
up surprisingly well:

- products answer "what am I selling?"
- prices answer "how do I charge for it?"
- meters answer "what are we counting?"
- access answers "what does the user currently have?"
- usage answers "what have they already spent?"

That is the real shape of billing in most SaaS products.
