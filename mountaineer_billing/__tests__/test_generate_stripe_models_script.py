import importlib.util
import json
import subprocess
import sys
from importlib import import_module
from pathlib import Path

from pydantic import BaseModel

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


def _make_schema(
    *,
    version: str,
    title: str,
    extra_schemas: dict[str, dict] | None = None,
    paths: dict | None = None,
) -> dict:
    component_schemas = {
        schema_name: {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
            },
            "required": ["id"],
        }
        for schema_name in (
            "event",
            "charge",
            "checkout.session",
            "customer",
            "invoice",
            "payment_intent",
            "price",
            "product",
            "subscription",
        )
    }
    if extra_schemas:
        component_schemas.update(extra_schemas)

    return {
        "openapi": "3.0.0",
        "info": {"title": title, "version": version},
        "paths": paths or {},
        "components": {"schemas": component_schemas},
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
                "if version >= '2026-01-01':",
                "    price_symbol = 'PriceModel'",
                "else:",
                "    price_symbol = 'Price'",
                "if version >= '2025-09-30':",
                "    subscription_symbol = 'SubscriptionModel'",
                "else:",
                "    subscription_symbol = 'Subscription'",
                "(output_dir / '_internal.py').write_text(",
                "    '\\n'.join([",
                "        'from pydantic import BaseModel',",
                "        '',",
                "        'class Event(BaseModel):',",
                "        '    id: str',",
                "        '',",
                "        'class ChargeModel(BaseModel):',",
                "        '    id: str',",
                "        '',",
                "        'class CustomerModel(BaseModel):',",
                "        '    id: str',",
                "        '',",
                "        'class InvoiceModel(BaseModel):',",
                "        '    id: str',",
                "        '',",
                "        'class PaymentIntent(BaseModel):',",
                "        '    id: str',",
                "        '',",
                "        f'class {price_symbol}(BaseModel):',",
                "        '    id: str',",
                "        '',",
                "        'class ProductModel(BaseModel):',",
                "        '    id: str',",
                "        '',",
                "        'class SubscriptionItem(BaseModel):',",
                "        f'    price: {price_symbol}',",
                "        '',",
                "        'class SubscriptionItems(BaseModel):',",
                "        '    data: list[SubscriptionItem]',",
                "        '',",
                "        f'class {subscription_symbol}(BaseModel):',",
                "        '    id: str',",
                "        '    items: SubscriptionItems | None = None',",
                "        '',",
                "        'class Session(BaseModel):',",
                "        '    id: str',",
                "        '',",
                "        'Event.model_rebuild()',",
                "        '',",
                "    ]) + '\\n'",
                ")",
                "(output_dir / 'checkout.py').write_text(",
                "    '\\n'.join([",
                "        'from ._internal import Session',",
                "        '',",
                "        '__all__ = [\"Session\"]',",
                "        '',",
                "    ])",
                ")",
                "(output_dir / 'test_helpers.py').write_text(",
                "    '\\n'.join([",
                "        'from pydantic import BaseModel, Field',",
                "        '',",
                "        'class Helper(BaseModel):',",
                "        '    id: str = Field(...)',",
                "        '',",
                "    ])",
                ")",
                "(output_dir / '__init__.py').write_text(",
                "    '\\n'.join([",
                "        f'# generated for {version} ({title})',",
                "        'from ._internal import (',",
                "        '    ChargeModel,',",
                "        '    CustomerModel,',",
                "        '    Event,',",
                "        '    InvoiceModel,',",
                "        '    PaymentIntent,',",
                "        f'    {price_symbol},',",
                "        '    ProductModel,',",
                "        f'    {subscription_symbol},',",
                "        ')',",
                "        '',",
                "        '__all__ = [',",
                "        '    \"ChargeModel\",',",
                "        '    \"CustomerModel\",',",
                "        '    \"Event\",',",
                "        '    \"InvoiceModel\",',",
                "        '    \"PaymentIntent\",',",
                "        f'    \"{price_symbol}\",',",
                "        '    \"ProductModel\",',",
                "        f'    \"{subscription_symbol}\",',",
                "        ']',",
                "        '',",
                "    ])",
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


def test_build_parser_accepts_no_fetch_alias():
    parser = stripe_codegen.build_parser()
    args = parser.parse_args(["--no-fetch"])

    assert args.skip_fetch is True


def test_collect_schema_revisions_prefers_latest_schema(tmp_path: Path):
    repo_dir = tmp_path / "stripe-openapi"
    repo_dir.mkdir()
    _init_repo(repo_dir)

    _write_json(
        repo_dir / "openapi" / "spec3.json",
        _make_schema(version="2022-12-31.basil", title="legacy-pre-cutoff"),
    )
    _commit_all(repo_dir, "legacy pre cutoff")

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

    revisions = stripe_codegen.filter_revisions_by_min_year(
        stripe_codegen.collect_schema_revisions(repo_dir),
        min_api_year=2023,
    )

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
        _make_schema(version="2022-12-31.basil", title="legacy-pre-cutoff"),
    )
    _commit_all(repo_dir, "legacy pre cutoff")

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
    latest_schema = json.loads(
        (output_dir / "v2026_02_25_clover" / "schema.json").read_text()
    )
    generated_types = (output_dir / "types.py").read_text()

    assert "legacy-two" in legacy_models
    assert "latest-ga" in latest_models
    assert (
        stripe_codegen.VERSION_DISCRIMINATOR_FIELD
        not in latest_schema["components"]["schemas"]["event"]["properties"]
    )
    assert (
        "from ._type_helpers import LazyAdapter, make_lazy_payload_type"
        in generated_types
    )
    assert "LazyStripeAdapter = LazyAdapter" in generated_types
    assert "TypeAdapter" not in generated_types
    assert (
        f'VERSION_DISCRIMINATOR_FIELD = "{stripe_codegen.VERSION_DISCRIMINATOR_FIELD}"'
        in generated_types
    )
    assert "if TYPE_CHECKING:" in generated_types
    assert "_MODEL_REGISTRY" in generated_types
    assert "class LazyStripeAdapter" not in generated_types
    assert "parse_object_payload" not in generated_types
    assert "parse_event_payload" not in generated_types
    assert "_OBJECT_MODEL_TYPES" not in generated_types
    assert (output_dir / "_type_helpers.py").exists()
    assert (output_dir / "__init__.py").exists()
    assert (
        (output_dir / "v2026_02_25_clover" / "__init__.py")
        .read_text()
        .startswith("from . import models")
    )
    assert (
        "ConfigDict(defer_build=True)"
        in (output_dir / "v2026_02_25_clover" / "models" / "_deferred.py").read_text()
    )
    assert (
        "model_rebuild()"
        not in (
            output_dir / "v2026_02_25_clover" / "models" / "_internal.py"
        ).read_text()
    )
    latest_internal = (
        output_dir / "v2026_02_25_clover" / "models" / "_internal.py"
    ).read_text()
    assert "from ._deferred import BaseModel" in latest_internal
    assert "MountaineerBillingApiVersion" not in latest_internal
    assert stripe_codegen.VERSION_DISCRIMINATOR_FIELD not in latest_internal
    assert stripe_codegen.VERSION_DISCRIMINATOR_FIELD in latest_models
    assert (
        stripe_codegen.VERSION_DISCRIMINATOR_FIELD
        in (output_dir / "v2026_02_25_clover" / "models" / "checkout.py").read_text()
    )
    assert (
        "from ._deferred import BaseModel, Field"
        in (
            output_dir / "v2026_02_25_clover" / "models" / "test_helpers.py"
        ).read_text()
    )


def test_generate_stripe_package_prunes_unreachable_components(tmp_path: Path):
    repo_dir = tmp_path / "stripe-openapi"
    repo_dir.mkdir()
    _init_repo(repo_dir)

    schema = _make_schema(
        version="2026-02-25.clover",
        title="latest-ga",
        extra_schemas={
            "customer_settings": {
                "type": "object",
                "properties": {
                    "default_source": {"$ref": "#/components/schemas/source"},
                },
            },
            "source": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
            "unused_model": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
            "path_only_model": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        },
        paths={
            "/unused": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/path_only_model"
                                    }
                                }
                            },
                        }
                    }
                }
            }
        },
    )
    schema["components"]["schemas"]["customer"]["properties"]["settings"] = {
        "$ref": "#/components/schemas/customer_settings"
    }

    _write_json(repo_dir / "latest" / "openapi.spec3.json", schema)
    _commit_all(repo_dir, "latest")

    output_dir = tmp_path / "generated"
    codegen_script = tmp_path / "fake_codegen.py"
    _fake_codegen_script(codegen_script)

    stripe_codegen.generate_stripe_package(
        repo_dir=repo_dir,
        output_dir=output_dir,
        codegen_command=str(codegen_script),
        fetch_repo=False,
    )

    pruned_schema = json.loads(
        (output_dir / "v2026_02_25_clover" / "schema.json").read_text()
    )
    pruned_components = pruned_schema["components"]["schemas"]

    assert "customer_settings" in pruned_components
    assert "source" in pruned_components
    assert "unused_model" not in pruned_components
    assert "path_only_model" not in pruned_components
    assert pruned_schema["paths"] == {}


def test_generate_stripe_package_uses_local_cpu_count_for_pool(
    tmp_path: Path, monkeypatch
):
    repo_dir = tmp_path / "stripe-openapi"
    repo_dir.mkdir()
    _init_repo(repo_dir)

    _write_json(
        repo_dir / "openapi" / "spec3.json",
        _make_schema(version="2025-01-01.acacia", title="legacy"),
    )
    _commit_all(repo_dir, "legacy")

    _write_json(
        repo_dir / "latest" / "openapi.spec3.json",
        _make_schema(version="2026-02-25.clover", title="latest"),
    )
    _commit_all(repo_dir, "latest")

    output_dir = tmp_path / "generated"
    codegen_script = tmp_path / "fake_codegen.py"
    _fake_codegen_script(codegen_script)

    pool_processes: list[int] = []

    class FakePool:
        def __init__(self, *, processes: int):
            pool_processes.append(processes)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def imap_unordered(self, func, iterable):
            for item in iterable:
                yield func(item)

    monkeypatch.setattr(stripe_codegen, "_local_cpu_count", lambda: 7)
    monkeypatch.setattr(
        stripe_codegen,
        "_pool_factory",
        lambda *, processes: FakePool(processes=processes),
    )

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
    assert pool_processes == [7]


def test_generated_types_module_resolves_version_specific_models(tmp_path: Path):
    repo_dir = tmp_path / "stripe-openapi"
    repo_dir.mkdir()
    _init_repo(repo_dir)

    _write_json(
        repo_dir / "openapi" / "spec3.json",
        _make_schema(version="2024-04-10", title="ga-older"),
    )
    _commit_all(repo_dir, "older")

    _write_json(
        repo_dir / "latest" / "openapi.spec3.json",
        _make_schema(version="2026-02-25.clover", title="ga-latest"),
    )
    _commit_all(repo_dir, "latest")

    output_dir = tmp_path / "generated"
    codegen_script = tmp_path / "fake_codegen.py"
    _fake_codegen_script(codegen_script)

    stripe_codegen.generate_stripe_package(
        repo_dir=repo_dir,
        output_dir=output_dir,
        codegen_command=str(codegen_script),
        fetch_repo=False,
    )

    sys.path.insert(0, str(tmp_path))
    try:
        generated_types = import_module("generated.types")
        version_field = stripe_codegen.VERSION_DISCRIMINATOR_FIELD

        older_subscription = generated_types.StripeSubscriptionAdapter.validate_python(
            {
                "id": "sub_old",
            },
            api_version="2024-04-10",
        )
        newer_subscription = generated_types.StripeSubscriptionAdapter.validate_python(
            {
                "id": "sub_new",
            },
            api_version="2026-02-25.clover",
        )
        older_price = generated_types.StripePriceAdapter.validate_python(
            {
                "id": "price_old",
            },
            api_version="2024-04-10",
        )
        newer_price = generated_types.StripePriceAdapter.validate_python(
            {
                "id": "price_new",
            },
            api_version="2026-02-25.clover",
        )
        checkout_session = generated_types.StripeCheckoutSessionAdapter.validate_python(
            {
                "id": "cs_test",
            },
            api_version="2026-02-25.clover",
        )
        event_payload = generated_types.StripeEventAdapter.validate_python(
            {
                "id": "evt_test",
            },
            api_version="2026-02-25.clover",
        )
        nested_subscription = generated_types.StripeSubscriptionAdapter.validate_python(
            {
                "id": "sub_nested",
                "items": {
                    "data": [
                        {
                            "price": {
                                "id": "price_nested",
                            }
                        }
                    ]
                },
            },
            api_version="2026-02-25.clover",
        )
        newer_subscription_type = (
            generated_types.StripeSubscriptionAdapter.model_type_for_api_version(
                "2026-02-25.clover"
            )
        )
        directly_validated = newer_subscription_type.model_validate(
            {"id": "sub_direct"}
        )

        class Wrapper(BaseModel):
            subscription: generated_types.StripeSubscriptionPayload

        wrapped = Wrapper(subscription=newer_subscription)
        serialized = wrapped.model_dump(mode="json")
        round_tripped = Wrapper.model_validate(serialized)

        assert older_subscription.__class__.__name__ == "Subscription"
        assert newer_subscription.__class__.__name__ == "SubscriptionModel"
        assert older_price.__class__.__name__ == "Price"
        assert newer_price.__class__.__name__ == "PriceModel"
        assert checkout_session.__class__.__name__ == "Session"
        assert event_payload.__class__.__name__ == "Event"
        assert nested_subscription.items is not None
        assert nested_subscription.items.data[0].price.id == "price_nested"
        assert directly_validated.mountaineer_billing_api_version == "2026-02-25.clover"
        assert serialized["subscription"][version_field] == "2026-02-25.clover"
        assert round_tripped.subscription.__class__.__name__ == "SubscriptionModel"
        assert not hasattr(generated_types, "parse_object_payload")
        assert not hasattr(generated_types, "parse_event_payload")
    finally:
        sys.path.remove(str(tmp_path))
