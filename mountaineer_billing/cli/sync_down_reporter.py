from __future__ import annotations

from contextlib import AbstractContextManager
from types import TracebackType
from typing import Protocol

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

from mountaineer_billing.logging import LOGGER


class SyncDownReporter(Protocol):
    """Shared reporter interface for Stripe sync-down progress updates."""

    def start_sync(self, *, api_version: str | None) -> None: ...

    def start_endpoint(self, *, object_type: str) -> None: ...

    def update_endpoint(
        self,
        *,
        object_type: str,
        synced_count: int,
        elapsed_seconds: float,
        objects_per_second: float,
    ) -> None: ...

    def complete_endpoint(
        self,
        *,
        object_type: str,
        synced_count: int,
        elapsed_seconds: float,
        objects_per_second: float,
    ) -> None: ...

    def queue_materialization(self, *, customer_count: int) -> None: ...

    def complete_sync(
        self,
        *,
        elapsed_seconds: float,
        total_synced: int,
        price_mappings_upserted: int,
        customers_enqueued: int,
    ) -> None: ...

    def warning(self, message: str, *args: object) -> None: ...


class LoggingSyncDownReporter:
    """Fallback reporter for `StripeSyncDown.sync_objects()` outside the Rich CLI path.

    This is the default when a caller invokes `sync_objects()` without injecting a
    reporter, which is the behavior used by tests and any programmatic or
    non-interactive entrypoints that want ordinary structured log lines instead of
    the `billing-sync down` terminal progress UI.
    """

    def start_sync(self, *, api_version: str | None) -> None:
        LOGGER.info(
            "Starting Stripe sync down using API version %s",
            api_version,
        )

    def start_endpoint(self, *, object_type: str) -> None:
        LOGGER.info("Syncing Stripe %s objects", object_type)

    def update_endpoint(
        self,
        *,
        object_type: str,
        synced_count: int,
        elapsed_seconds: float,
        objects_per_second: float,
    ) -> None:
        from mountaineer_billing.cli.sync_down import format_duration

        LOGGER.info(
            "Stripe %s sync progress: %s objects synced in %s at %.1f objects/sec",
            object_type,
            synced_count,
            format_duration(elapsed_seconds),
            objects_per_second,
        )

    def complete_endpoint(
        self,
        *,
        object_type: str,
        synced_count: int,
        elapsed_seconds: float,
        objects_per_second: float,
    ) -> None:
        from mountaineer_billing.cli.sync_down import format_duration

        LOGGER.info(
            "Synced %s Stripe %s objects in %s at %.1f objects/sec",
            synced_count,
            object_type,
            format_duration(elapsed_seconds),
            objects_per_second,
        )

    def queue_materialization(self, *, customer_count: int) -> None:
        LOGGER.info(
            "Queueing subscription materialization for %s customers",
            customer_count,
        )

    def complete_sync(
        self,
        *,
        elapsed_seconds: float,
        total_synced: int,
        price_mappings_upserted: int,
        customers_enqueued: int,
    ) -> None:
        from mountaineer_billing.cli.sync_down import format_duration

        LOGGER.info(
            "Completed Stripe sync down in %s: %s Stripe objects synced, %s price mappings upserted, %s customers enqueued",
            format_duration(elapsed_seconds),
            total_synced,
            price_mappings_upserted,
            customers_enqueued,
        )

    def warning(self, message: str, *args: object) -> None:
        LOGGER.warning(message, *args)


class RichSyncDownReporter(AbstractContextManager["RichSyncDownReporter"]):
    """Terminal progress reporter for the interactive `billing-sync down` command."""

    def __init__(self, *, console: Console | None = None):
        self.console = console or Console(stderr=True)
        self.progress = Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("{task.description:<18}"),
            BarColumn(bar_width=20, style="cyan", pulse_style="cyan"),
            TextColumn("{task.fields[synced]:>10} synced"),
            TextColumn("{task.fields[rate]:>8} /s", style="dim"),
            TimeElapsedColumn(),
            console=self.console,
            auto_refresh=False,
            transient=False,
        )
        self.task_ids: dict[str, TaskID] = {}

    def __enter__(self) -> RichSyncDownReporter:
        self.progress.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.progress.stop()
        return None

    def start_sync(self, *, api_version: str | None) -> None:
        self.console.print(
            f"Stripe sync down using API version {api_version}",
            style="bold",
        )

    def start_endpoint(self, *, object_type: str) -> None:
        self.task_ids[object_type] = self.progress.add_task(
            object_type,
            total=None,
            synced="0",
            rate="0.0",
        )
        self.progress.refresh()

    def update_endpoint(
        self,
        *,
        object_type: str,
        synced_count: int,
        elapsed_seconds: float,
        objects_per_second: float,
    ) -> None:
        del elapsed_seconds
        self.progress.update(
            self.task_ids[object_type],
            synced=f"{synced_count:,}",
            rate=f"{objects_per_second:.1f}",
        )
        self.progress.refresh()

    def complete_endpoint(
        self,
        *,
        object_type: str,
        synced_count: int,
        elapsed_seconds: float,
        objects_per_second: float,
    ) -> None:
        del elapsed_seconds
        task_id = self.task_ids[object_type]
        completed = max(synced_count, 1)
        self.progress.update(
            task_id,
            total=completed,
            completed=completed,
            synced=f"{synced_count:,}",
            rate=f"{objects_per_second:.1f}",
        )
        self.progress.stop_task(task_id)
        self.progress.refresh()

    def queue_materialization(self, *, customer_count: int) -> None:
        self.console.print(
            f"Queueing subscription materialization for {customer_count:,} customers",
            style="dim",
        )

    def complete_sync(
        self,
        *,
        elapsed_seconds: float,
        total_synced: int,
        price_mappings_upserted: int,
        customers_enqueued: int,
    ) -> None:
        from mountaineer_billing.cli.sync_down import format_duration

        self.console.print(
            "Stripe sync down complete in "
            f"{format_duration(elapsed_seconds)} "
            f"({total_synced:,} objects, {price_mappings_upserted:,} price mappings, "
            f"{customers_enqueued:,} customers enqueued)",
            style="bold",
        )

    def warning(self, message: str, *args: object) -> None:
        formatted_message = message % args if args else message
        self.console.print(f"Warning: {formatted_message}", style="yellow")


__all__ = [
    "LoggingSyncDownReporter",
    "RichSyncDownReporter",
    "SyncDownReporter",
]
