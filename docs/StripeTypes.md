# Stripe Types

This project needs two things from Stripe payload typing that pull in opposite directions:

1. Static type checking should see all supported Stripe API versions at once so our code is forced to stay compatible across versions.
2. Runtime import cost should stay low, because eagerly importing every generated Stripe model package is expensive.

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

- mypy / pyright should reason about all generated versions together
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

The generated model modules are post-processed so they import `BaseModel`, `RootModel`, and `Field` from a local `_deferred.py` shim instead of directly from Pydantic.

That shim sets:

```python
ConfigDict(defer_build=True)
```

The point is not to avoid importing the selected module. The point is to avoid eagerly building every nested validator graph inside that module during import. We still load the chosen version lazily, but we also keep the selected module's startup cost lower.

## Schema Pruning Before Codegen

We do not generate Python models from the entire Stripe OpenAPI schema.

Before `datamodel-code-generator` runs, `scripts/generate_stripe_models.py` calls `_prune_schema_for_codegen(...)`. That function:

- starts from the root schema objects we care about
- walks transitive `$ref` dependencies from those roots
- keeps only reachable `components.schemas`
- clears `paths`, because endpoint descriptions are not needed for payload validation

This is an intentional scope reduction. We are not trying to provide a complete Stripe SDK. We are trying to validate and store the subset of Stripe object families that our billing system actually uses.

That keeps the generated code:

- smaller
- faster to import
- easier to regenerate
- easier to reason about during cross-version compatibility work

## What Static Checking Buys Us

The important architectural bet here is that application code should be written against the intersection of fields that are safe across the versions we support.

Because the type aliases expand to unions during static analysis, code that depends on fields or shapes that are not stable across versions should become visible during type checking instead of failing later when a different Stripe API version arrives.

In other words:

- runtime chooses one concrete version lazily
- static analysis forces us to respect all supported versions together

## Relevant Files

- `scripts/generate_stripe_models.py`: collects Stripe schema revisions, prunes schema scope, generates model packages, and renders `stripe/types.py`
- `mountaineer_billing/type_helpers.py`: lazy validation and serialization plumbing
- `mountaineer_billing/stripe/types.py`: runtime registry plus `TYPE_CHECKING` unions
- `mountaineer_billing/__tests__/test_generate_stripe_models_script.py`: generation invariants
- `mountaineer_billing/__tests__/test_stripe_types.py`: runtime round-trip and performance regression coverage
