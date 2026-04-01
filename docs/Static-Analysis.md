# Stripe Types

Stripe provides an OpenAPI definition that lets clients generate native-language bindings for their objects. Which is great! Less great is that their API changes
with some frequency and we want to statically prove that `mountaineer-billing` works across the whole set of APIs that we support. For this reason we basically
want to always use a polymorphic definition of the Stripe values. Consider for subscriptions:

```python
fn has_right_subscription(subscription: StripeSubscription):
    ...
```

Behind the scenes we actually have something like: `StripeSubscription = StripeSubscriptionV1 | StripeSubscriptionV2 | StripeSubscriptionV3 | etc.`.

If we try to access a value on subscription that is only valid in some of these API versions, `ty` will throw an error and force us to build more robust
access patterns for this field.

Because of this polymorphic need, we need two things from Stripe payload typing that pull in opposite directions:

1. Static type checking should see all supported Stripe API versions at once so our code is forced to stay compatible across versions.
2. Runtime import cost should stay low, because eagerly importing every generated Stripe model package is expensive because of the amount of helper objects they have as part of their API.

Our solution is to separate the static typing story from the runtime validation story.

## Goal

We generate versioned Pydantic packages under `mountaineer_billing/stripe/v*/models` and expose repo-level aliases in `mountaineer_billing/stripe/types.py`.

Those aliases represent payload families we actually store and operate on:

- `event`
- `charge`
- `checkout.session`
- `customer`
- `invoice`
- `payment_intent`
- `price`
- `product`
- `subscription`

The design goal is:

- ty should reason about all generated versions together
- runtime should only import the specific Stripe version needed for the payload being validated

## Why We Do Not Use A Normal `TypeAdapter`

The straightforward implementation is a discriminated union like:

```python
StripeEventPayload = Annotated[
    v2023_08_16_event | v2024_04_03_event | ...,
    Field(discriminator="mountaineer_billing_api_version"),
]
StripeEventAdapter = TypeAdapter(StripeEventPayload)
```

That works functionally, but it has the wrong runtime behavior for this project:

- every generated model module must be imported up front
- Pydantic builds the full discriminated-union validator eagerly
- import time grows with every additional Stripe version we support
- importing `mountaineer_billing.stripe.types` becomes coupled to the entire generated model tree

That is the opposite of what we want in normal app startup paths.

## Static Types Versus Runtime Types

`mountaineer_billing/stripe/types.py` deliberately behaves differently depending on whether code is being type-checked or executed.

Under `TYPE_CHECKING`:

- each alias is a real union of all generated versions
- static analyzers can see the entire supported surface area
- if our application code accesses a field that is not present across the union, type checking should complain

At runtime:

- those aliases are replaced with lightweight wrapper types built by `make_lazy_payload_type(...)`
- the wrapper delegates validation to `LazyAdapter`
- `LazyAdapter` reads the payload's Stripe API version and imports only that version's generated model module

This gives us the important property we want:

- static analysis is broad
- runtime loading is narrow

## Runtime Validation Flow

The runtime pieces live in:

- `mountaineer_billing/type_helpers.py`
- `mountaineer_billing/stripe/types.py`

`LazyAdapter` keeps a registry from `(payload family, api_version)` to `(module path, symbol name)`.

When `validate_python(...)` runs:

1. We determine the Stripe API version from the explicit `api_version=` argument or from the injected `mountaineer_billing_api_version` discriminator field.
2. We import only the model module for that specific version.
3. We validate with that concrete Pydantic model.
4. We cache the loaded model class so repeated validations for the same version are cheap.

On serialization, `LazyAdapter` adds `mountaineer_billing_api_version` back into the JSON payload when needed so the value round-trips cleanly through storage.

## Why Generated Models Use `defer_build=True`

We do a bit of post-processing in `generate_stripe_models.py` that isn't done by the default code generation pipeline. Specifically the generated model modules are post-processed so they import `BaseModel`, `RootModel`, and `Field` from a local `_deferred.py` shim instead of directly from Pydantic.

That shim sets:

```python
ConfigDict(defer_build=True)
```

This lets us avoid eagerly building every nested validator graph inside that module during import. We still load the chosen version lazily, but we also keep the selected module's startup cost lower. We then defer until the lazy logic above.

## Schema Pruning Before Codegen

As an additional saver of the overall size of our generated code, we don't generate Python models from the entire Stripe OpenAPI schema.

Before `datamodel-code-generator` runs, `scripts/generate_stripe_models.py` calls `_prune_schema_for_codegen(...)`. That function:

- starts from the root schema objects we care about
- walks transitive `$ref` dependencies from those roots
- keeps only reachable `components.schemas`
- clears `paths`, because endpoint descriptions are not needed for payload validation

That keeps the generated code:

- smaller
- faster to import
- easier to regenerate
- easier to reason about during cross-version compatibility work
