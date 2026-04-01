# AGENTS

## Stripe Typing

- Prefer direct dot access on Stripe payload models from `mountaineer_billing/stripe/types.py`.
- The generated Stripe payload aliases are versioned unions during static analysis. Using dot access lets the type checker verify that a field exists across every version in the union.
- Do not default to `getattr(...)` for Stripe payload access. It hides real schema differences and prevents the checker from catching incompatible field usage.
- Use `getattr(...)` only when we have already confirmed a real cross-version mismatch in the generated Stripe models, or when a helper must handle multiple runtime wrapper shapes such as plain strings, `RootModel` id wrappers, and expanded Stripe objects.
- Example: top-level `Subscription.current_period_start` existed in older Stripe versions but was removed in newer ones, so that access must use a guarded fallback. By contrast, common fields like `id`, `status`, `items`, `payment_status`, and similar fields should use direct attribute access.
