from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module
from types import UnionType
from typing import Annotated, Any, ClassVar, Generic, TypeVar, Union, cast, get_args, get_origin

from pydantic import BaseModel
from pydantic_core import core_schema as pydantic_core_schema

ValidatedModel = TypeVar("ValidatedModel")
ModelImportTarget = tuple[str, str]
ModelRegistry = Mapping[str, ModelImportTarget]


def _serialize_validated_model(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


class LazyAdapter(Generic[ValidatedModel]):
    def __init__(
        self,
        *,
        registry: ModelRegistry,
        discriminator_field: str,
        package: str | None,
        label: str,
    ):
        self._registry = dict(registry)
        self._discriminator_field = discriminator_field
        self._package = package
        self._label = label
        self._model_cache: dict[str, type[BaseModel]] = {}
        self._discriminator_cache: dict[type[BaseModel], str] = {}

    def validate_python(
        self,
        value: Any,
        *,
        api_version: str | None = None,
    ) -> ValidatedModel:
        if isinstance(value, BaseModel):
            if self._is_registered_model_instance(value):
                return cast(ValidatedModel, value)
            value = value.model_dump(mode="python")

        if not isinstance(value, Mapping):
            raise TypeError(
                f"Expected a mapping or BaseModel for {self._label!r}, "
                f"got {type(value).__name__}"
            )

        discriminator_value = api_version
        payload_discriminator = value.get(self._discriminator_field)
        if discriminator_value is None:
            if not isinstance(payload_discriminator, str):
                raise ValueError(
                    "Stripe payload is missing a string "
                    f"{self._discriminator_field!r} discriminator"
                )
            discriminator_value = payload_discriminator
        elif (
            payload_discriminator is not None
            and payload_discriminator != discriminator_value
        ):
            raise ValueError(
                "Stripe payload discriminator does not match the provided "
                f"api_version for {self._label!r}"
            )

        model_type = self._load_model(discriminator_value)
        return cast(ValidatedModel, model_type.model_validate(value))

    def core_schema(self) -> pydantic_core_schema.CoreSchema:
        return pydantic_core_schema.no_info_plain_validator_function(
            self.validate_python,
            serialization=pydantic_core_schema.plain_serializer_function_ser_schema(
                self.serialize_python,
                return_schema=pydantic_core_schema.any_schema(),
                when_used="always",
            ),
        )

    def serialize_python(self, value: Any) -> Any:
        if not isinstance(value, BaseModel):
            return value

        serialized = _serialize_validated_model(value)
        if isinstance(serialized, Mapping) and self._discriminator_field in serialized:
            return serialized

        discriminator_value = self._discriminator_for_model_instance(value)
        if discriminator_value is None:
            return serialized

        return {
            self._discriminator_field: discriminator_value,
            **serialized,
        }

    def _load_model(self, discriminator_value: str) -> type[BaseModel]:
        try:
            return self._model_cache[discriminator_value]
        except KeyError:
            pass

        try:
            module_path, symbol_name = self._registry[discriminator_value]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported Stripe API version {discriminator_value!r} "
                f"for {self._label!r}"
            ) from exc

        model_module = import_module(module_path, package=self._package)
        model_type = cast(type[BaseModel], getattr(model_module, symbol_name))
        self._rebuild_model(model_type, model_module)
        self._model_cache[discriminator_value] = model_type
        return model_type

    def _rebuild_model(
        self,
        model_type: type[BaseModel],
        model_module: Any,
    ) -> None:
        internal_namespace: dict[str, Any] = {}
        module_name = getattr(model_module, "__name__", "")
        if module_name:
            try:
                internal_module = import_module(f"{module_name}._internal")
            except ModuleNotFoundError:
                try:
                    package_name, _, _ = module_name.rpartition(".")
                    internal_module = (
                        import_module(f"{package_name}._internal")
                        if package_name
                        else None
                    )
                except ModuleNotFoundError:
                    internal_module = None
            if internal_module is not None:
                internal_namespace = dict(vars(internal_module))

        model_type.model_rebuild(
            _types_namespace={
                "Annotated": Annotated,
                **internal_namespace,
                **dict(vars(model_module)),
            },
            force=True,
            raise_errors=False,
        )

    def model_type_for_api_version(self, api_version: str) -> type[BaseModel]:
        return self._load_model(api_version)

    def _fully_qualified_module_path(self, module_path: str) -> str:
        if module_path.startswith("."):
            if not self._package:
                raise ValueError(
                    "Relative model import paths require a package context"
                )
            return f"{self._package}{module_path}"
        return module_path

    def _is_registered_model_instance(self, value: BaseModel) -> bool:
        if any(
            isinstance(value, model_type) for model_type in self._model_cache.values()
        ):
            return True

        return self._discriminator_for_model_instance(value) is not None

    def _discriminator_for_model_instance(self, value: BaseModel) -> str | None:
        model_type = value.__class__
        try:
            return self._discriminator_cache[model_type]
        except KeyError:
            pass

        value_module = model_type.__module__
        value_name = model_type.__name__
        for discriminator_value, (module_path, symbol_name) in self._registry.items():
            if value_name != symbol_name:
                continue
            qualified_module = self._fully_qualified_module_path(module_path)
            if value_module in {qualified_module, f"{qualified_module}._internal"}:
                self._discriminator_cache[model_type] = discriminator_value
                return discriminator_value
        return None


class LazyPayloadBase:
    adapter: ClassVar[LazyAdapter[Any]]

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: Any,
    ) -> pydantic_core_schema.CoreSchema:
        return cls.adapter.core_schema()

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema_value: pydantic_core_schema.CoreSchema,
        handler: Any,
    ) -> dict[str, Any]:
        return {
            "type": "object",
            "title": cls.__name__,
        }


class LazyPayloadAnnotation:
    def __init__(self, *, name: str, adapter: LazyAdapter[Any]):
        self.name = name
        self.adapter = adapter

    def __get_pydantic_core_schema__(
        self,
        source_type: Any,
        handler: Any,
    ) -> pydantic_core_schema.CoreSchema:
        schema = self.adapter.core_schema()
        if _allows_none(source_type):
            return pydantic_core_schema.nullable_schema(schema)
        return schema

    def __get_pydantic_json_schema__(
        self,
        core_schema_value: pydantic_core_schema.CoreSchema,
        handler: Any,
    ) -> dict[str, Any]:
        return {
            "type": "object",
            "title": self.name,
        }


def _allows_none(source_type: Any) -> bool:
    origin = get_origin(source_type)
    if origin not in {Union, UnionType}:
        return False

    return any(arg is type(None) for arg in get_args(source_type))


def make_lazy_payload_type(
    name: str,
    adapter: LazyAdapter[Any],
    *,
    module_name: str,
    nullable: bool = False,
) -> Any:
    payload_type: Any = dict[str, Any] | None if nullable else dict[str, Any]
    return Annotated[
        payload_type,
        LazyPayloadAnnotation(name=name, adapter=adapter),
    ]


__all__ = [
    "LazyAdapter",
    "LazyPayloadAnnotation",
    "LazyPayloadBase",
    "make_lazy_payload_type",
]
