from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from types import ModuleType


@dataclass(frozen=True, slots=True)
class StripeVersionMetadata:
    api_version: str
    commit_sha: str
    schema_path: str
    package_name: str


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, StripeVersionMetadata]:
    registry_path = Path(__file__).with_name("versions.json")
    if not registry_path.exists():
        return {}

    raw_entries = json.loads(registry_path.read_text())
    return {
        entry["api_version"]: StripeVersionMetadata(**entry) for entry in raw_entries
    }


def available_versions() -> tuple[str, ...]:
    return tuple(_load_registry())


def get_version_metadata(api_version: str) -> StripeVersionMetadata:
    try:
        return _load_registry()[api_version]
    except KeyError as exc:
        raise KeyError(
            f"Stripe API version {api_version!r} has not been generated"
        ) from exc


def import_models(api_version: str) -> ModuleType:
    metadata = get_version_metadata(api_version)
    return import_module(f"{__name__}.{metadata.package_name}.models")


def refresh_registry() -> None:
    _load_registry.cache_clear()


__all__ = [
    "StripeVersionMetadata",
    "available_versions",
    "get_version_metadata",
    "import_models",
    "refresh_registry",
]
