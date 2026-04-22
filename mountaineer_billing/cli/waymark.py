from __future__ import annotations

from typing import Any, Protocol, cast


class SupportsNonBlockingRun(Protocol):
    async def __call__(
        self,
        *args: Any,
        _blocking: bool = True,
        _priority: int | None = None,
        **kwargs: Any,
    ) -> Any: ...


async def run_workflow_nonblocking(workflow_run: object, /, **kwargs: Any) -> Any:
    return await cast(SupportsNonBlockingRun, workflow_run)(
        _blocking=False,
        **kwargs,
    )
