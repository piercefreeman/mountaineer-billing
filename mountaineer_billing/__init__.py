from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable

import mountaineer_di.resolver_core as resolver_core
from mountaineer_di.resolver_core import DependencyResolver


def _patch_mountaineer_di_provide_dependencies() -> None:
    if getattr(resolver_core, "_mountaineer_provide_dependencies_patched", False):
        return

    @asynccontextmanager
    async def _compat_provide_dependencies(
        func: Callable[..., Any],
        kwargs: dict[str, Any] | None = None,
        *,
        request: Any | None = None,
        path: str | None = None,
        dependency_overrides: dict[Callable[..., Any], Callable[..., Any]]
        | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        resolver = DependencyResolver(
            kwargs,
            request=request,
            path=path,
            dependency_overrides=dependency_overrides,
        )
        try:
            call_kwargs = await resolver.build_call_kwargs(func)
            yield call_kwargs
        except BaseException as exc:
            suppress = await resolver._stack.__aexit__(  # type: ignore[attr-defined]
                type(exc),
                exc,
                exc.__traceback__,
            )
            if not suppress:
                raise
        else:
            await resolver.close()

    resolver_core.provide_dependencies = _compat_provide_dependencies
    resolver_core._mountaineer_provide_dependencies_patched = True


_patch_mountaineer_di_provide_dependencies()

from mountaineer_billing import dependencies as BillingDependencies  # noqa: F401
from mountaineer_billing.config import BillingConfig as BillingConfig
from mountaineer_billing.enums import (
    PriceBillingInterval as PriceBillingInterval,
    StripeStatus as StripeStatus,
    StripeWebhookType as StripeWebhookType,
    SyncStatus as SyncStatus,
)
from mountaineer_billing.exceptions import ResourceExhausted as ResourceExhausted
from mountaineer_billing.models import (
    BillingProjectionState as BillingProjectionState,
    CheckoutSession as CheckoutSession,
    MeteredUsage as MeteredUsage,
    Payment as Payment,
    ProductPrice as ProductPrice,
    ResourceAccess as ResourceAccess,
    StripeEvent as StripeEvent,
    StripeObject as StripeObject,
    Subscription as Subscription,
    UserBillingMixin as UserBillingMixin,
)
from mountaineer_billing.products import (
    CountDownMeteredAllocation as CountDownMeteredAllocation,
    LicensedProduct as LicensedProduct,
    MeteredDefinition as MeteredDefinition,
    MeteredIDBase as MeteredIDBase,
    MeteredProduct as MeteredProduct,
    Price as Price,
    PriceIDBase as PriceIDBase,
    ProductBase as ProductBase,
    ProductIDBase as ProductIDBase,
    RollupType as RollupType,
)
