#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "datamodel-code-generator>=0.35.0",
# ]
# ///

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO_URL = "https://github.com/stripe/openapi.git"
DEFAULT_SCHEMA_PATHS = (
    "latest/openapi.spec3.json",
    "preview/openapi.spec3.json",
    "openapi/spec3.json",
)
DEFAULT_REPO_DIR = REPO_ROOT / ".cache" / "stripe-openapi"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "mountaineer_billing" / "stripe"
PATH_PRIORITY = {
    "latest/openapi.spec3.json": 0,
    "preview/openapi.spec3.json": 1,
    "openapi/spec3.json": 2,
}


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


def _run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
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


def collect_schema_revisions(
    repo_dir: Path,
    *,
    include_preview: bool = False,
) -> list[StripeSchemaRevision]:
    schema_paths = _schema_paths(include_preview)
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

    for commit_index, commit_sha in enumerate(raw_commits):
        for schema_path in sorted(schema_paths, key=lambda path: PATH_PRIORITY[path]):
            if commit_sha not in commits_by_path[schema_path]:
                continue

            raw_schema = _git_output(repo_dir, "show", f"{commit_sha}:{schema_path}")
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
            "    registry_path = Path(__file__).with_name(\"versions.json\")",
            "    if not registry_path.exists():",
            "        return {}",
            "",
            "    raw_entries = json.loads(registry_path.read_text())",
            "    return {",
            "        entry[\"api_version\"]: StripeVersionMetadata(**entry)",
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
            "            f\"Stripe API version {api_version!r} has not been generated\"",
            "        ) from exc",
            "",
            "",
            "def import_models(api_version: str) -> ModuleType:",
            "    metadata = get_version_metadata(api_version)",
            "    return import_module(f\"{__name__}.{metadata.package_name}.models\")",
            "",
            "",
            "def refresh_registry() -> None:",
            "    _load_registry.cache_clear()",
            "",
            "",
            "__all__ = [",
            "    \"StripeVersionMetadata\",",
            "    \"available_versions\",",
            "    \"get_version_metadata\",",
            "    \"import_models\",",
            "    \"refresh_registry\",",
            "]",
            "",
        ]
    )


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


def _prepare_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for child in output_dir.iterdir():
        if not child.is_dir():
            continue
        if not child.name.startswith("v"):
            continue
        shutil.rmtree(child)


def _load_schema(repo_dir: Path, revision: StripeSchemaRevision) -> dict[str, Any]:
    raw_schema = _git_output(repo_dir, "show", f"{revision.commit_sha}:{revision.schema_path}")
    return json.loads(raw_schema)


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
    _run_command(command)


def ensure_repo(
    repo_dir: Path,
    *,
    repo_url: str = DEFAULT_REPO_URL,
    fetch: bool = True,
) -> Path:
    if not fetch:
        if not (repo_dir / ".git").exists():
            raise FileNotFoundError(f"Git repository not found: {repo_dir}")
        return repo_dir

    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    if not (repo_dir / ".git").exists():
        _run_command(["git", "clone", repo_url, str(repo_dir)], cwd=repo_dir.parent)
    else:
        _run_command(
            ["git", "fetch", "--force", "--tags", "--prune", "--refetch", "origin"],
            cwd=repo_dir,
        )

    return repo_dir


def generate_stripe_package(
    *,
    repo_dir: Path = DEFAULT_REPO_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    repo_url: str = DEFAULT_REPO_URL,
    codegen_command: str | None = None,
    include_preview: bool = False,
    selected_versions: set[str] | None = None,
    fetch_repo: bool = True,
) -> list[StripeSchemaRevision]:
    repo_dir = ensure_repo(repo_dir, repo_url=repo_url, fetch=fetch_repo)
    revisions = collect_schema_revisions(repo_dir, include_preview=include_preview)

    if selected_versions:
        revisions = [
            revision
            for revision in revisions
            if revision.api_version in selected_versions
        ]

    if not revisions:
        raise RuntimeError("No Stripe schemas found for generation")

    _prepare_output_dir(output_dir)
    (output_dir / "__init__.py").write_text(_render_package_root_init())
    codegen_command_parts = _codegen_command_parts(codegen_command)

    for revision in revisions:
        package_dir = output_dir / revision.package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        schema = _load_schema(repo_dir, revision)
        schema_path = package_dir / "schema.json"
        schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
        (package_dir / "__init__.py").write_text(_render_version_package_init(revision))

        _generate_models(
            schema_path=schema_path,
            output_dir=package_dir / "models",
            codegen_command=codegen_command_parts,
        )

    (output_dir / "versions.json").write_text(_render_registry(revisions))
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
        "--api-version",
        action="append",
        dest="api_versions",
        help="Only generate the specified Stripe API version. Repeat as needed.",
    )
    parser.add_argument(
        "--skip-fetch",
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
        selected_versions=set(args.api_versions) if args.api_versions else None,
        fetch_repo=not args.skip_fetch,
    )
    sys.stdout.write(
        f"Generated {len(revisions)} Stripe API package(s) into {Path(args.output_dir)}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
