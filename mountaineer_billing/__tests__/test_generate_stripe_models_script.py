import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "generate_stripe_models.py"
)


def _load_script_module():
    spec = importlib.util.spec_from_file_location("generate_stripe_models", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


stripe_codegen = _load_script_module()


def _run(command: list[str], cwd: Path) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _make_schema(*, version: str, title: str) -> dict:
    return {
        "openapi": "3.0.0",
        "info": {"title": title, "version": version},
        "paths": {},
        "components": {"schemas": {}},
    }


def _commit_all(repo_dir: Path, message: str) -> str:
    _run(["git", "add", "."], cwd=repo_dir)
    _run(["git", "commit", "-m", message], cwd=repo_dir)
    return _run(["git", "rev-parse", "HEAD"], cwd=repo_dir)


def _init_repo(repo_dir: Path) -> None:
    _run(["git", "init"], cwd=repo_dir)
    _run(["git", "config", "user.email", "tests@example.com"], cwd=repo_dir)
    _run(["git", "config", "user.name", "Tests"], cwd=repo_dir)


def _fake_codegen_script(script_path: Path) -> None:
    script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "import sys",
                "from pathlib import Path",
                "",
                "args = sys.argv[1:]",
                "input_path = Path(args[args.index('--input') + 1])",
                "output_dir = Path(args[args.index('--output') + 1])",
                "schema = json.loads(input_path.read_text())",
                "title = schema['info']['title']",
                "version = schema['info']['version']",
                "output_dir.mkdir(parents=True, exist_ok=True)",
                "(output_dir / '__init__.py').write_text(",
                "    f\"# generated for {version} ({title})\\n\"",
                "    \"from pydantic import BaseModel\\n\\n\"",
                "    \"class GeneratedModel(BaseModel):\\n\"",
                "    \"    pass\\n\"",
                ")",
                "",
            ]
        )
    )
    script_path.chmod(0o755)


def test_package_name_for_version():
    assert stripe_codegen.package_name_for_version("2026-02-25.clover") == (
        "v2026_02_25_clover"
    )
    assert stripe_codegen.package_name_for_version(
        "2026-03-04.preview; embedded_connect_beta=v2"
    ) == ("v2026_03_04_preview_embedded_connect_beta_v2")


def test_collect_schema_revisions_prefers_latest_schema(tmp_path: Path):
    repo_dir = tmp_path / "stripe-openapi"
    repo_dir.mkdir()
    _init_repo(repo_dir)

    _write_json(
        repo_dir / "openapi" / "spec3.json",
        _make_schema(version="2025-01-01.acacia", title="legacy-one"),
    )
    _commit_all(repo_dir, "legacy one")

    _write_json(
        repo_dir / "openapi" / "spec3.json",
        _make_schema(version="2025-01-01.acacia", title="legacy-two"),
    )
    legacy_sha = _commit_all(repo_dir, "legacy two")

    _write_json(
        repo_dir / "latest" / "openapi.spec3.json",
        _make_schema(version="2026-02-25.clover", title="latest-ga"),
    )
    latest_sha = _commit_all(repo_dir, "latest ga")

    _write_json(
        repo_dir / "openapi" / "spec3.json",
        _make_schema(version="2026-02-25.clover", title="legacy-should-not-win"),
    )
    _commit_all(repo_dir, "legacy duplicate")

    revisions = stripe_codegen.collect_schema_revisions(repo_dir)

    assert [revision.api_version for revision in revisions] == [
        "2025-01-01.acacia",
        "2026-02-25.clover",
    ]
    assert revisions[0].commit_sha == legacy_sha
    assert revisions[0].schema_path == "openapi/spec3.json"
    assert revisions[1].commit_sha == latest_sha
    assert revisions[1].schema_path == "latest/openapi.spec3.json"


def test_generate_stripe_package_writes_versioned_modules(tmp_path: Path):
    repo_dir = tmp_path / "stripe-openapi"
    repo_dir.mkdir()
    _init_repo(repo_dir)

    _write_json(
        repo_dir / "openapi" / "spec3.json",
        _make_schema(version="2025-01-01.acacia", title="legacy-two"),
    )
    _commit_all(repo_dir, "legacy")

    _write_json(
        repo_dir / "latest" / "openapi.spec3.json",
        _make_schema(version="2026-02-25.clover", title="latest-ga"),
    )
    _commit_all(repo_dir, "latest")

    output_dir = tmp_path / "generated"
    codegen_script = tmp_path / "fake_codegen.py"
    _fake_codegen_script(codegen_script)

    revisions = stripe_codegen.generate_stripe_package(
        repo_dir=repo_dir,
        output_dir=output_dir,
        codegen_command=str(codegen_script),
        fetch_repo=False,
    )

    assert [revision.package_name for revision in revisions] == [
        "v2025_01_01_acacia",
        "v2026_02_25_clover",
    ]

    registry = json.loads((output_dir / "versions.json").read_text())
    assert [entry["api_version"] for entry in registry] == [
        "2025-01-01.acacia",
        "2026-02-25.clover",
    ]

    legacy_models = (
        output_dir / "v2025_01_01_acacia" / "models" / "__init__.py"
    ).read_text()
    latest_models = (
        output_dir / "v2026_02_25_clover" / "models" / "__init__.py"
    ).read_text()

    assert "legacy-two" in legacy_models
    assert "latest-ga" in latest_models
    assert (output_dir / "__init__.py").exists()
    assert (output_dir / "v2026_02_25_clover" / "__init__.py").read_text().startswith(
        "from . import models"
    )
