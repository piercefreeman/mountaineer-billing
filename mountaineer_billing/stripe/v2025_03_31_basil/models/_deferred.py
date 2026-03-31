from __future__ import annotations

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
