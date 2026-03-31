#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "datamodel-code-generator>=0.35.0",
#   "rich>=13.9.0",
# ]
# ///

from __future__ import annotations

import argparse
import json
import multiprocessing
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO_URL = "https://github.com/stripe/openapi.git"
DEFAULT_SCHEMA_PATHS = (
    "latest/openapi.spec3.json",
    "preview/openapi.spec3.json",
    "openapi/spec3.json",
)
DEFAULT_MIN_API_YEAR = 2023
DEFAULT_REPO_DIR = REPO_ROOT / ".cache" / "stripe-openapi"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "mountaineer_billing" / "stripe"
TYPE_HELPERS_SOURCE_PATH = REPO_ROOT / "mountaineer_billing" / "type_helpers.py"
PATH_PRIORITY = {
    "latest/openapi.spec3.json": 0,
    "preview/openapi.spec3.json": 1,
    "openapi/spec3.json": 2,
}
HEARTBEAT_SECONDS = 10.0
CONSOLE = Console()
VERSION_DISCRIMINATOR_FIELD = "mountaineer_billing_api_version"
SCHEMA_REF_PREFIX = "#/components/schemas/"
SUPPORTED_STRIPE_OBJECT_TYPES = (
    "charge",
    "checkout.session",
    "customer",
    "invoice",
    "payment_intent",
    "price",
    "product",
    "subscription",
)
SCHEMA_KEYS_BY_OBJECT_TYPE = {
    "event": "event",
    "charge": "charge",
    "checkout.session": "checkout.session",
    "customer": "customer",
    "invoice": "invoice",
    "payment_intent": "payment_intent",
    "price": "price",
    "product": "product",
    "subscription": "subscription",
}
TYPE_IMPORT_CANDIDATES: dict[str, tuple[tuple[str, str], ...]] = {
    "event": (("models", "Event"),),
    "charge": (("models", "ChargeModel"), ("models", "Charge")),
    "checkout.session": (
        ("models.checkout", "Session"),
        ("models._internal", "Session"),
    ),
    "customer": (("models", "CustomerModel"), ("models", "Customer")),
    "invoice": (("models", "InvoiceModel"), ("models", "Invoice")),
    "payment_intent": (
        ("models", "PaymentIntentModel"),
        ("models", "PaymentIntent"),
    ),
    "price": (("models", "PriceModel"), ("models", "Price")),
    "product": (("models", "ProductModel"), ("models", "Product")),
    "subscription": (
        ("models", "SubscriptionModel"),
        ("models", "Subscription"),
    ),
}
TYPE_ALIAS_NAMES = {
    "event": "StripeEventPayload",
    "charge": "StripeChargePayload",
    "checkout.session": "StripeCheckoutSessionPayload",
    "customer": "StripeCustomerPayload",
    "invoice": "StripeInvoicePayload",
    "payment_intent": "StripePaymentIntentPayload",
    "price": "StripePricePayload",
    "product": "StripeProductPayload",
    "subscription": "StripeSubscriptionPayload",
}
TYPE_ADAPTER_NAMES = {
    "event": "StripeEventAdapter",
    "charge": "StripeChargeAdapter",
    "checkout.session": "StripeCheckoutSessionAdapter",
    "customer": "StripeCustomerAdapter",
    "invoice": "StripeInvoiceAdapter",
    "payment_intent": "StripePaymentIntentAdapter",
    "price": "StripePriceAdapter",
    "product": "StripeProductAdapter",
    "subscription": "StripeSubscriptionAdapter",
}
DEFERRED_PYDANTIC_IMPORTS = {"BaseModel", "Field", "RootModel"}
MODEL_REBUILD_PATTERN = re.compile(r"(?m)^[A-Za-z_][A-Za-z0-9_]*\.model_rebuild\(\)\n?")
PYDANTIC_IMPORT_PATTERN = re.compile(r"(?m)^from pydantic import (?P<imports>.+)$")
TYPING_IMPORT_PATTERN = re.compile(r"(?m)^from typing import (?P<imports>.+)$")
DEFERRED_MODELS_MODULE = """from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field
from pydantic import RootModel as PydanticRootModel

RootModelRootType = TypeVar("RootModelRootType")


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(defer_build=True)


class RootModel(PydanticRootModel[RootModelRootType], Generic[RootModelRootType]):
    model_config = ConfigDict(defer_build=True)


__all__ = ["BaseModel", "Field", "RootModel"]
"""


@dataclass(frozen=True, slots=True)
class StripeSchemaRevision:
    api_version: str
    commit_sha: str
    schema_path: str
    package_name: str


@dataclass(frozen=True, slots=True)
class _RankedRevision:
    revision: StripeSchemaRevision
    commit_index: int
    path_priority: int


@dataclass(frozen=True, slots=True)
class StripeTypeImport:
    api_version: str
    package_name: str
    object_type: str
    import_path: str
    symbol_name: str
    alias_name: str


@dataclass(frozen=True, slots=True)
class _RevisionGenerationTask:
    repo_dir: Path
    output_dir: Path
    revision: StripeSchemaRevision
    codegen_command: tuple[str, ...]


def _run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    description: str | None = None,
) -> subprocess.CompletedProcess[str]:
    if description is None:
        try:
            return subprocess.run(
                command,
                cwd=cwd,
                check=check,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else ""
            stdout = exc.stdout.strip() if exc.stdout else ""
            details = stderr or stdout or "command failed"
            raise RuntimeError(f"{shlex.join(command)}: {details}") from exc

    started = monotonic()
    CONSOLE.log(f"[cyan]{description}[/cyan]")

    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        while True:
            try:
                stdout, stderr = process.communicate(timeout=HEARTBEAT_SECONDS)
                break
            except subprocess.TimeoutExpired:
                elapsed = monotonic() - started
                CONSOLE.log(
                    f"[dim]{description} is still running ({elapsed:.0f}s elapsed)[/dim]"
                )
        if check and process.returncode:
            raise subprocess.CalledProcessError(
                process.returncode,
                command,
                output=stdout,
                stderr=stderr,
            )
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        stdout = exc.stdout.strip() if exc.stdout else ""
        details = stderr or stdout or "command failed"
        raise RuntimeError(f"{shlex.join(command)}: {details}") from exc


def _git_output(repo_dir: Path, *args: str) -> str:
    result = _run_command(["git", *args], cwd=repo_dir)
    return result.stdout


def _schema_paths(include_preview: bool) -> tuple[str, ...]:
    if include_preview:
        return DEFAULT_SCHEMA_PATHS

    return tuple(
        schema_path
        for schema_path in DEFAULT_SCHEMA_PATHS
        if not schema_path.startswith("preview/")
    )


def package_name_for_version(api_version: str) -> str:
    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", api_version).strip("_").lower()
    if not normalized:
        normalized = "unknown"
    return f"v{normalized}"


def api_version_year(api_version: str) -> int | None:
    match = re.match(r"^(?P<year>\d{4})-\d{2}-\d{2}", api_version)
    if not match:
        return None
    return int(match.group("year"))


def filter_revisions_by_min_year(
    revisions: list[StripeSchemaRevision],
    *,
    min_api_year: int,
) -> list[StripeSchemaRevision]:
    return [
        revision
        for revision in revisions
        if (api_year := api_version_year(revision.api_version)) is not None
        and api_year >= min_api_year
    ]


def collect_schema_revisions(
    repo_dir: Path,
    *,
    include_preview: bool = False,
) -> list[StripeSchemaRevision]:
    schema_paths = _schema_paths(include_preview)
    CONSOLE.log(
        f"[cyan]Scanning git history for schema revisions in[/cyan] [bold]{repo_dir}[/bold]"
    )
    raw_commits = _git_output(
        repo_dir,
        "rev-list",
        "--reverse",
        "HEAD",
        "--",
        *schema_paths,
    ).splitlines()

    if not raw_commits:
        return []

    commits_by_path = {
        schema_path: set(
            _git_output(
                repo_dir,
                "rev-list",
                "--reverse",
                "HEAD",
                "--",
                schema_path,
            ).splitlines()
        )
        for schema_path in schema_paths
    }
    revisions_by_version: dict[str, _RankedRevision] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=CONSOLE,
    ) as progress:
        scan_task = progress.add_task("Scanning schema commits", total=len(raw_commits))

        for commit_index, commit_sha in enumerate(raw_commits):
            for schema_path in sorted(
                schema_paths, key=lambda path: PATH_PRIORITY[path]
            ):
                if commit_sha not in commits_by_path[schema_path]:
                    continue

                raw_schema = _git_output(
                    repo_dir, "show", f"{commit_sha}:{schema_path}"
                )
                schema = json.loads(raw_schema)
                api_version = schema["info"]["version"]
                ranked_revision = _RankedRevision(
                    revision=StripeSchemaRevision(
                        api_version=api_version,
                        commit_sha=commit_sha,
                        schema_path=schema_path,
                        package_name=package_name_for_version(api_version),
                    ),
                    commit_index=commit_index,
                    path_priority=PATH_PRIORITY[schema_path],
                )
                current = revisions_by_version.get(api_version)
                if (
                    current is None
                    or ranked_revision.path_priority < current.path_priority
                    or (
                        ranked_revision.path_priority == current.path_priority
                        and ranked_revision.commit_index >= current.commit_index
                    )
                ):
                    revisions_by_version[api_version] = ranked_revision

            progress.advance(scan_task)
            if (commit_index + 1) % 25 == 0 or commit_index + 1 == len(raw_commits):
                progress.update(
                    scan_task,
                    description=(
                        "Scanning schema commits "
                        f"({len(revisions_by_version)} versions found)"
                    ),
                )

    return [
        ranked_revision.revision
        for ranked_revision in sorted(
            revisions_by_version.values(),
            key=lambda item: (
                item.commit_index,
                item.path_priority,
                item.revision.api_version,
            ),
        )
    ]


def _render_registry(revisions: list[StripeSchemaRevision]) -> str:
    serialized = [
        {
            "api_version": revision.api_version,
            "commit_sha": revision.commit_sha,
            "schema_path": revision.schema_path,
            "package_name": revision.package_name,
        }
        for revision in revisions
    ]
    return json.dumps(serialized, indent=2, sort_keys=True) + "\n"


def _render_package_root_init() -> str:
    return "\n".join(
        [
            "from __future__ import annotations",
            "",
            "import json",
            "from dataclasses import dataclass",
            "from functools import lru_cache",
            "from importlib import import_module",
            "from pathlib import Path",
            "from types import ModuleType",
            "",
            "",
            "@dataclass(frozen=True, slots=True)",
            "class StripeVersionMetadata:",
            "    api_version: str",
            "    commit_sha: str",
            "    schema_path: str",
            "    package_name: str",
            "",
            "",
            "@lru_cache(maxsize=1)",
            "def _load_registry() -> dict[str, StripeVersionMetadata]:",
            '    registry_path = Path(__file__).with_name("versions.json")',
            "    if not registry_path.exists():",
            "        return {}",
            "",
            "    raw_entries = json.loads(registry_path.read_text())",
            "    return {",
            '        entry["api_version"]: StripeVersionMetadata(**entry)',
            "        for entry in raw_entries",
            "    }",
            "",
            "",
            "def available_versions() -> tuple[str, ...]:",
            "    return tuple(_load_registry())",
            "",
            "",
            "def get_version_metadata(api_version: str) -> StripeVersionMetadata:",
            "    try:",
            "        return _load_registry()[api_version]",
            "    except KeyError as exc:",
            "        raise KeyError(",
            '            f"Stripe API version {api_version!r} has not been generated"',
            "        ) from exc",
            "",
            "",
            "def import_models(api_version: str) -> ModuleType:",
            "    metadata = get_version_metadata(api_version)",
            '    return import_module(f"{__name__}.{metadata.package_name}.models")',
            "",
            "",
            "def refresh_registry() -> None:",
            "    _load_registry.cache_clear()",
            "",
            "",
            "__all__ = [",
            '    "StripeVersionMetadata",',
            '    "available_versions",',
            '    "get_version_metadata",',
            '    "import_models",',
            '    "refresh_registry",',
            "]",
            "",
        ]
    )


def _iter_schema_refs(value: Any):
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            yield ref
        for nested_value in value.values():
            yield from _iter_schema_refs(nested_value)
    elif isinstance(value, list):
        for nested_value in value:
            yield from _iter_schema_refs(nested_value)


def _schema_key_from_ref(ref: str) -> str | None:
    if not ref.startswith(SCHEMA_REF_PREFIX):
        return None
    return ref[len(SCHEMA_REF_PREFIX) :]


def _prune_schema_for_codegen(schema: dict[str, Any]) -> dict[str, Any]:
    components = schema.get("components")
    if not isinstance(components, dict):
        raise RuntimeError("Stripe OpenAPI schema is missing components")

    schema_components = components.get("schemas")
    if not isinstance(schema_components, dict):
        raise RuntimeError("Stripe OpenAPI schema is missing components.schemas")

    root_schema_keys = tuple(dict.fromkeys(SCHEMA_KEYS_BY_OBJECT_TYPE.values()))
    pending_schema_keys = list(root_schema_keys)
    reachable_schema_keys: set[str] = set()

    while pending_schema_keys:
        schema_key = pending_schema_keys.pop()
        if schema_key in reachable_schema_keys:
            continue

        component = schema_components.get(schema_key)
        if not isinstance(component, dict):
            raise RuntimeError(
                f"Stripe OpenAPI schema is missing schema component {schema_key!r}"
            )

        reachable_schema_keys.add(schema_key)
        for ref in _iter_schema_refs(component):
            ref_schema_key = _schema_key_from_ref(ref)
            if ref_schema_key and ref_schema_key not in reachable_schema_keys:
                pending_schema_keys.append(ref_schema_key)

    schema["paths"] = {}
    schema["components"] = {
        "schemas": {
            schema_key: schema_components[schema_key]
            for schema_key in schema_components
            if schema_key in reachable_schema_keys
        }
    }
    return schema


def _module_file_for_import(package_dir: Path, import_path: str) -> Path:
    if import_path == "models":
        return package_dir / "models" / "__init__.py"
    return package_dir / Path(*import_path.split(".")).with_suffix(".py")


def _module_contains_symbol(module_path: Path, symbol_name: str) -> bool:
    if not module_path.exists():
        return False
    pattern = rf"\b{re.escape(symbol_name)}\b"
    return re.search(pattern, module_path.read_text()) is not None


def _type_import_alias(package_name: str, object_type: str) -> str:
    normalized_object_type = re.sub(r"[^0-9a-zA-Z]+", "_", object_type).strip("_")
    return f"{package_name}_{normalized_object_type}"


def _resolve_type_import(
    *,
    output_dir: Path,
    revision: StripeSchemaRevision,
    object_type: str,
) -> StripeTypeImport:
    package_dir = output_dir / revision.package_name
    for import_path, symbol_name in TYPE_IMPORT_CANDIDATES[object_type]:
        module_path = _module_file_for_import(package_dir, import_path)
        if _module_contains_symbol(module_path, symbol_name):
            return StripeTypeImport(
                api_version=revision.api_version,
                package_name=revision.package_name,
                object_type=object_type,
                import_path=f".{revision.package_name}.{import_path}",
                symbol_name=symbol_name,
                alias_name=_type_import_alias(revision.package_name, object_type),
            )

    raise RuntimeError(
        "Could not resolve generated Stripe type import for "
        f"{object_type!r} in {revision.package_name}"
    )


def _can_import_global_type_helpers(output_dir: Path) -> bool:
    package_root = output_dir.parent
    return (package_root / "__init__.py").exists() and (
        package_root / "type_helpers.py"
    ).exists()


def _render_type_helpers_import(output_dir: Path) -> str:
    if _can_import_global_type_helpers(output_dir):
        return "from ..type_helpers import LazyAdapter, make_lazy_payload_type"
    return "from ._type_helpers import LazyAdapter, make_lazy_payload_type"


def _ensure_types_helper_module(output_dir: Path) -> None:
    helper_output_path = output_dir / "_type_helpers.py"
    if _can_import_global_type_helpers(output_dir):
        if helper_output_path.exists():
            helper_output_path.unlink()
        return

    helper_output_path.write_text(TYPE_HELPERS_SOURCE_PATH.read_text())


def _render_types_module(
    *,
    output_dir: Path,
    revisions: list[StripeSchemaRevision],
) -> str:
    imports_by_object_type: dict[str, list[StripeTypeImport]] = {}
    for object_type in ("event", *SUPPORTED_STRIPE_OBJECT_TYPES):
        imports_by_object_type[object_type] = [
            _resolve_type_import(
                output_dir=output_dir,
                revision=revision,
                object_type=object_type,
            )
            for revision in revisions
        ]

    import_lines = [
        f"from {type_import.import_path} import "
        f"{type_import.symbol_name} as {type_import.alias_name}"
        for type_import in sorted(
            (
                type_import
                for type_imports in imports_by_object_type.values()
                for type_import in type_imports
            ),
            key=lambda value: (value.import_path, value.alias_name),
        )
    ]

    object_types = ("event", *SUPPORTED_STRIPE_OBJECT_TYPES)
    runtime_registry_lines = [
        "_MODEL_REGISTRY: dict[str, dict[str, tuple[str, str]]] = {",
    ]
    for object_type in object_types:
        runtime_registry_lines.extend(
            [
                f'    "{object_type}": {{',
                *[
                    (
                        f'        "{type_import.api_version}": '
                        f'("{type_import.import_path}", "{type_import.symbol_name}"),'
                    )
                    for type_import in imports_by_object_type[object_type]
                ],
                "    },",
            ]
        )
    runtime_registry_lines.extend(["}", ""])

    lines = [
        "# ruff: noqa: I001",
        "from __future__ import annotations",
        "",
        "from typing import TYPE_CHECKING, Any, TypeAlias",
        "",
        _render_type_helpers_import(output_dir),
        "",
        f'VERSION_DISCRIMINATOR_FIELD = "{VERSION_DISCRIMINATOR_FIELD}"',
        "",
        *runtime_registry_lines,
        "",
        "LazyStripeAdapter = LazyAdapter",
        "",
        "if TYPE_CHECKING:",
        *[f"    {line}" for line in import_lines],
        "",
    ]

    for object_type in object_types:
        alias_name = TYPE_ALIAS_NAMES[object_type]
        type_imports = imports_by_object_type[object_type]
        lines.extend(
            [
                f"    {alias_name}: TypeAlias = (",
                "        "
                + " | ".join(type_import.alias_name for type_import in type_imports),
                "    )",
                "",
            ]
        )

    lines.extend(
        [
            "    StripeObjectPayload: TypeAlias = (",
            "        "
            + " | ".join(
                TYPE_ALIAS_NAMES[object_type]
                for object_type in SUPPORTED_STRIPE_OBJECT_TYPES
            ),
            "    )",
            "else:",
            "    StripeObjectPayload = Any",
            "",
            "_ADAPTERS: dict[str, LazyAdapter[Any]] = {",
            *[
                "    "
                f'"{object_type}": LazyAdapter('
                f"registry=_MODEL_REGISTRY[{object_type!r}], "
                f"discriminator_field=VERSION_DISCRIMINATOR_FIELD, "
                "package=__package__, "
                f"label={object_type!r}),"
                for object_type in object_types
            ],
            "}",
            "",
        ]
    )

    for object_type in object_types:
        alias_name = TYPE_ALIAS_NAMES[object_type]
        adapter_name = TYPE_ADAPTER_NAMES[object_type]
        lines.extend(
            [
                f'{adapter_name}: LazyAdapter[{alias_name}] = _ADAPTERS["{object_type}"]',
                "",
            ]
        )

    lines.append("if not TYPE_CHECKING:")
    for object_type in object_types:
        alias_name = TYPE_ALIAS_NAMES[object_type]
        adapter_name = TYPE_ADAPTER_NAMES[object_type]
        lines.extend(
            [
                f"    {alias_name} = make_lazy_payload_type(",
                f'        "{alias_name}",',
                f"        {adapter_name},",
                "        module_name=__name__,",
                "    )",
                "",
            ]
        )

    all_names = [
        TYPE_ALIAS_NAMES["event"],
        *[
            TYPE_ALIAS_NAMES[object_type]
            for object_type in SUPPORTED_STRIPE_OBJECT_TYPES
        ],
        "StripeObjectPayload",
        "LazyAdapter",
        "LazyStripeAdapter",
        TYPE_ADAPTER_NAMES["event"],
        *[
            TYPE_ADAPTER_NAMES[object_type]
            for object_type in SUPPORTED_STRIPE_OBJECT_TYPES
        ],
    ]
    lines.extend(
        [
            "__all__ = [",
            *[f'    "{name}",' for name in all_names],
            "]",
            "",
        ]
    )

    return "\n".join(lines)


def _render_version_package_init(revision: StripeSchemaRevision) -> str:
    return "\n".join(
        [
            "from . import models",
            "",
            f'API_VERSION = "{revision.api_version}"',
            f'COMMIT_SHA = "{revision.commit_sha}"',
            f'SCHEMA_PATH = "{revision.schema_path}"',
            "",
            '__all__ = ["API_VERSION", "COMMIT_SHA", "SCHEMA_PATH", "models"]',
            "",
        ]
    )


def _prepare_output_dir(
    output_dir: Path,
    *,
    selected_package_names: set[str] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for child in output_dir.iterdir():
        if not child.is_dir():
            continue
        if not child.name.startswith("v"):
            continue
        if (
            selected_package_names is not None
            and child.name not in selected_package_names
        ):
            continue
        shutil.rmtree(child)


def _load_schema(repo_dir: Path, revision: StripeSchemaRevision) -> dict[str, Any]:
    raw_schema = _git_output(
        repo_dir, "show", f"{revision.commit_sha}:{revision.schema_path}"
    )
    schema = json.loads(raw_schema)
    return _prune_schema_for_codegen(schema)


def _default_codegen_command() -> list[str]:
    return [sys.executable, "-m", "datamodel_code_generator"]


def _codegen_command_parts(codegen_command: str | None) -> list[str]:
    if codegen_command:
        return shlex.split(codegen_command)
    return _default_codegen_command()


def _generate_models(
    *,
    schema_path: Path,
    output_dir: Path,
    codegen_command: list[str],
    api_version: str,
    show_progress: bool = True,
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)

    command = [
        *codegen_command,
        "--input",
        str(schema_path),
        "--input-file-type",
        "openapi",
        "--output",
        str(output_dir),
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--target-python-version",
        "3.11",
        "--use-standard-collections",
        "--use-annotated",
        "--disable-timestamp",
    ]
    _run_command(
        command,
        description=(
            f"Running datamodel-code-generator for Stripe {api_version}"
            if show_progress
            else None
        ),
    )


def _deferred_import_path(*, models_dir: Path, generated_file: Path) -> str:
    relative_parts = generated_file.relative_to(models_dir).parts[:-1]
    return "." * (len(relative_parts) + 1) + "_deferred"


def _rewrite_pydantic_imports(
    source: str,
    *,
    models_dir: Path,
    generated_file: Path,
) -> str:
    deferred_import = _deferred_import_path(
        models_dir=models_dir,
        generated_file=generated_file,
    )

    def replace_import(match: re.Match[str]) -> str:
        imported_names = [name.strip() for name in match.group("imports").split(",")]
        deferred_names = [
            name for name in imported_names if name in DEFERRED_PYDANTIC_IMPORTS
        ]
        if not deferred_names:
            return match.group(0)

        remaining_names = [
            name for name in imported_names if name not in DEFERRED_PYDANTIC_IMPORTS
        ]
        rewritten_lines: list[str] = []
        if remaining_names:
            rewritten_lines.append(f"from pydantic import {', '.join(remaining_names)}")
        rewritten_lines.append(
            f"from {deferred_import} import {', '.join(deferred_names)}"
        )
        return "\n".join(rewritten_lines)

    return PYDANTIC_IMPORT_PATTERN.sub(replace_import, source)


def _ensure_typing_import(source: str, import_name: str) -> str:
    def replace_import(match: re.Match[str]) -> str:
        imported_names = [name.strip() for name in match.group("imports").split(",")]
        if import_name not in imported_names:
            imported_names.append(import_name)
        return f"from typing import {', '.join(imported_names)}"

    rewritten_source, count = TYPING_IMPORT_PATTERN.subn(
        replace_import, source, count=1
    )
    if count:
        return rewritten_source

    future_import = "from __future__ import annotations\n"
    if future_import in source:
        return source.replace(
            future_import,
            future_import + f"\nfrom typing import {import_name}\n",
            1,
        )
    return f"from typing import {import_name}\n" + source


def _resolve_package_model_target(
    *,
    package_dir: Path,
    object_type: str,
) -> tuple[Path, str]:
    for import_path, symbol_name in TYPE_IMPORT_CANDIDATES[object_type]:
        module_path = _module_file_for_import(package_dir, import_path)
        if _module_contains_symbol(module_path, symbol_name):
            return module_path, symbol_name

    raise RuntimeError(
        f"Could not resolve generated Stripe type import for {object_type!r}"
    )


def _inject_root_model_versions(
    *,
    package_dir: Path,
    api_version: str,
) -> None:
    wrappers_by_module: dict[Path, list[str]] = {}
    for object_type in ("event", *SUPPORTED_STRIPE_OBJECT_TYPES):
        module_path, symbol_name = _resolve_package_model_target(
            package_dir=package_dir,
            object_type=object_type,
        )
        wrappers_by_module.setdefault(module_path, []).append(symbol_name)

    for module_path, symbol_names in wrappers_by_module.items():
        source = _ensure_typing_import(module_path.read_text(), "Literal")
        wrapper_lines = ["", ""]
        for symbol_name in symbol_names:
            original_symbol_name = f"_MountaineerBillingOriginal{symbol_name}"
            wrapper_lines.extend(
                [
                    f"{original_symbol_name} = {symbol_name}",
                    "",
                    f"class {symbol_name}({original_symbol_name}):",
                    (
                        f"    {VERSION_DISCRIMINATOR_FIELD}: "
                        f"Literal[{api_version!r}] = {api_version!r}"
                    ),
                    "",
                ]
            )
        module_path.write_text(source + "\n".join(wrapper_lines))


def _postprocess_generated_models(models_dir: Path) -> None:
    (models_dir / "_deferred.py").write_text(DEFERRED_MODELS_MODULE)

    for generated_file in models_dir.rglob("*.py"):
        if generated_file.name == "_deferred.py":
            continue

        original_source = generated_file.read_text()
        rewritten_source = MODEL_REBUILD_PATTERN.sub("", original_source)
        rewritten_source = _rewrite_pydantic_imports(
            rewritten_source,
            models_dir=models_dir,
            generated_file=generated_file,
        )

        if rewritten_source != original_source:
            generated_file.write_text(rewritten_source)


def _local_cpu_count() -> int:
    try:
        return max(1, multiprocessing.cpu_count())
    except NotImplementedError:
        return 1


def _pool_factory(*, processes: int):
    if sys.platform != "win32":
        try:
            return multiprocessing.get_context("fork").Pool(processes=processes)
        except ValueError:
            pass
    return multiprocessing.Pool(processes=processes)


def _generate_revision_package(task: _RevisionGenerationTask) -> StripeSchemaRevision:
    revision = task.revision
    package_dir = task.output_dir / revision.package_name
    package_dir.mkdir(parents=True, exist_ok=True)

    schema = _load_schema(task.repo_dir, revision)
    schema_path = package_dir / "schema.json"
    schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    (package_dir / "__init__.py").write_text(_render_version_package_init(revision))

    _generate_models(
        schema_path=schema_path,
        output_dir=package_dir / "models",
        codegen_command=list(task.codegen_command),
        api_version=revision.api_version,
        show_progress=False,
    )
    _postprocess_generated_models(package_dir / "models")
    _inject_root_model_versions(
        package_dir=package_dir,
        api_version=revision.api_version,
    )
    return revision


def ensure_repo(
    repo_dir: Path,
    *,
    repo_url: str = DEFAULT_REPO_URL,
    fetch: bool = True,
) -> Path:
    if not fetch:
        if not (repo_dir / ".git").exists():
            raise FileNotFoundError(f"Git repository not found: {repo_dir}")
        CONSOLE.log(
            f"[cyan]Using existing Stripe OpenAPI checkout[/cyan] [bold]{repo_dir}[/bold]"
        )
        return repo_dir

    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    if not (repo_dir / ".git").exists():
        _run_command(
            ["git", "clone", repo_url, str(repo_dir)],
            cwd=repo_dir.parent,
            description=f"Cloning Stripe OpenAPI repo into {repo_dir}",
        )
    else:
        _run_command(
            ["git", "fetch", "--force", "--tags", "--prune", "--refetch", "origin"],
            cwd=repo_dir,
            description=f"Fetching latest Stripe OpenAPI history in {repo_dir}",
        )

    return repo_dir


def generate_stripe_package(
    *,
    repo_dir: Path = DEFAULT_REPO_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    repo_url: str = DEFAULT_REPO_URL,
    codegen_command: str | None = None,
    include_preview: bool = False,
    min_api_year: int = DEFAULT_MIN_API_YEAR,
    selected_versions: set[str] | None = None,
    fetch_repo: bool = True,
) -> list[StripeSchemaRevision]:
    CONSOLE.rule("[bold blue]Stripe Model Generation")
    CONSOLE.log(f"[cyan]Repo checkout:[/cyan] [bold]{repo_dir}[/bold]")
    CONSOLE.log(f"[cyan]Output dir:[/cyan] [bold]{output_dir}[/bold]")
    CONSOLE.log(f"[cyan]Minimum API year:[/cyan] [bold]{min_api_year}[/bold]")

    repo_dir = ensure_repo(repo_dir, repo_url=repo_url, fetch=fetch_repo)
    all_revisions = collect_schema_revisions(repo_dir, include_preview=include_preview)
    all_revisions = filter_revisions_by_min_year(
        all_revisions, min_api_year=min_api_year
    )

    revisions = all_revisions
    if selected_versions:
        revisions = [
            revision
            for revision in all_revisions
            if revision.api_version in selected_versions
        ]

    if not revisions:
        raise RuntimeError("No Stripe schemas found for generation")

    CONSOLE.log(
        f"[green]Found {len(revisions)} Stripe API version(s) to generate[/green]"
    )
    selected_package_names = (
        {revision.package_name for revision in revisions} if selected_versions else None
    )
    _prepare_output_dir(
        output_dir,
        selected_package_names=selected_package_names,
    )
    (output_dir / "__init__.py").write_text(_render_package_root_init())
    codegen_command_parts = tuple(_codegen_command_parts(codegen_command))
    generation_tasks = [
        _RevisionGenerationTask(
            repo_dir=repo_dir,
            output_dir=output_dir,
            revision=revision,
            codegen_command=codegen_command_parts,
        )
        for revision in revisions
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=CONSOLE,
    ) as progress:
        generate_task = progress.add_task(
            "Generating versioned Stripe packages", total=len(revisions)
        )

        pool_size = _local_cpu_count()
        progress.update(
            generate_task,
            description=(
                f"Generating versioned Stripe packages "
                f"({pool_size} workers, {len(revisions)} versions)"
            ),
        )

        if len(generation_tasks) == 1:
            _generate_revision_package(generation_tasks[0])
            progress.advance(generate_task)
        else:
            with _pool_factory(processes=pool_size) as pool:
                for _ in pool.imap_unordered(
                    _generate_revision_package,
                    generation_tasks,
                ):
                    progress.advance(generate_task)

    renderable_revisions = [
        revision
        for revision in all_revisions
        if (output_dir / revision.package_name / "models").exists()
    ]
    _ensure_types_helper_module(output_dir)
    (output_dir / "versions.json").write_text(_render_registry(renderable_revisions))
    (output_dir / "types.py").write_text(
        _render_types_module(output_dir=output_dir, revisions=renderable_revisions)
    )
    CONSOLE.log(
        f"[green]Wrote Stripe model registry to[/green] [bold]{output_dir}[/bold]"
    )
    return revisions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate versioned Pydantic models from Stripe's OpenAPI history."
    )
    parser.add_argument(
        "--repo-dir",
        default=str(DEFAULT_REPO_DIR),
        help="Local checkout path for stripe/openapi.",
    )
    parser.add_argument(
        "--repo-url",
        default=DEFAULT_REPO_URL,
        help="Git repository to clone or fetch.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory to write mountaineer_billing.stripe packages into.",
    )
    parser.add_argument(
        "--codegen-command",
        default=None,
        help="Override the OpenAPI-to-Pydantic command.",
    )
    parser.add_argument(
        "--include-preview",
        action="store_true",
        help="Include preview Stripe schemas in addition to GA and legacy specs.",
    )
    parser.add_argument(
        "--min-api-year",
        type=int,
        default=DEFAULT_MIN_API_YEAR,
        help="Only generate Stripe API versions whose year is at least this value.",
    )
    parser.add_argument(
        "--api-version",
        action="append",
        dest="api_versions",
        help="Only generate the specified Stripe API version. Repeat as needed.",
    )
    parser.add_argument(
        "--skip-fetch",
        "--no-fetch",
        dest="skip_fetch",
        action="store_true",
        help="Use an existing local git checkout without cloning or fetching.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    revisions = generate_stripe_package(
        repo_dir=Path(args.repo_dir),
        output_dir=Path(args.output_dir),
        repo_url=args.repo_url,
        codegen_command=args.codegen_command,
        include_preview=args.include_preview,
        min_api_year=args.min_api_year,
        selected_versions=set(args.api_versions) if args.api_versions else None,
        fetch_repo=not args.skip_fetch,
    )
    sys.stdout.write(
        f"Generated {len(revisions)} Stripe API package(s) into {Path(args.output_dir)}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
