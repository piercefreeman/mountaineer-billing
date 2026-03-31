#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from time import perf_counter

IMPORT_TIME_PATTERN = re.compile(
    r"^import time:\s+(?P<self_us>\d+)\s+\|\s+(?P<cumulative_us>\d+)\s+\|\s+(?P<module>.+)$"
)
DEFAULT_MODULES = (
    "mountaineer_billing.stripe.types",
    "mountaineer_billing.models",
)


@dataclass(frozen=True, slots=True)
class ImportStat:
    module: str
    self_us: int
    cumulative_us: int


def parse_import_stats(raw_output: str) -> list[ImportStat]:
    stats: list[ImportStat] = []
    for line in raw_output.splitlines():
        match = IMPORT_TIME_PATTERN.match(line)
        if not match:
            continue
        stats.append(
            ImportStat(
                module=match.group("module").strip(),
                self_us=int(match.group("self_us")),
                cumulative_us=int(match.group("cumulative_us")),
            )
        )
    return stats


def format_microseconds(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}s"
    if value >= 1_000:
        return f"{value / 1_000:.2f}ms"
    return f"{value}us"


def top_stats(stats: list[ImportStat], *, key: str, limit: int) -> list[ImportStat]:
    return sorted(stats, key=lambda stat: getattr(stat, key), reverse=True)[:limit]


def run_import_profile(module_name: str, *, timeout_seconds: int) -> tuple[float, str]:
    command = [
        sys.executable,
        "-X",
        "importtime",
        "-c",
        f"import {module_name}",
    ]

    with tempfile.TemporaryFile(mode="w+") as stderr_file:
        started = perf_counter()
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=stderr_file,
            text=True,
            timeout=timeout_seconds,
        )
        elapsed = perf_counter() - started

        stderr_file.seek(0)
        raw_stderr = stderr_file.read()

    if completed.returncode != 0:
        stdout = completed.stdout.strip()
        details = raw_stderr.strip() or stdout or "import failed"
        raise RuntimeError(f"{module_name}: {details}")

    # Python's import profiler writes to stderr.
    return elapsed, raw_stderr


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure Python module import time using -X importtime."
    )
    parser.add_argument(
        "modules",
        nargs="*",
        default=list(DEFAULT_MODULES),
        help="Module paths to import-profile.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=15,
        help="How many modules to show in the self/cumulative summaries.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Subprocess timeout per module, in seconds.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    for module_name in args.modules:
        sys.stdout.write(f"== {module_name} ==\n")
        try:
            elapsed, raw_profile = run_import_profile(
                module_name,
                timeout_seconds=args.timeout,
            )
        except subprocess.TimeoutExpired:
            sys.stdout.write(f"Timed out after {args.timeout}s\n\n")
            continue
        except RuntimeError as exc:
            sys.stdout.write(f"{exc}\n\n")
            continue

        stats = parse_import_stats(raw_profile)
        sys.stdout.write(f"Wall clock: {elapsed:.2f}s\n")
        sys.stdout.write("Top cumulative:\n")
        for stat in top_stats(stats, key="cumulative_us", limit=args.top):
            sys.stdout.write(
                f"  {format_microseconds(stat.cumulative_us):>10}  "
                f"{format_microseconds(stat.self_us):>10}  {stat.module}\n"
            )
        sys.stdout.write("Top self:\n")
        for stat in top_stats(stats, key="self_us", limit=args.top):
            sys.stdout.write(
                f"  {format_microseconds(stat.self_us):>10}  "
                f"{format_microseconds(stat.cumulative_us):>10}  {stat.module}\n"
            )
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
