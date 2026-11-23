from __future__ import annotations

from dataclasses import dataclass

from src_common.conventions.model_name import GENERATED_MODEL_PREFIX

from .protocol import GzModelNameTransformProtocol
from .scaffold import ScaffoldPrefixGzModelNameTransform


@dataclass(kw_only=True, frozen=True)
class ProductionGzModelNameTransform(GzModelNameTransformProtocol):
    prefix: str = GENERATED_MODEL_PREFIX

    def __call__(self, x: str) -> str:
        return ScaffoldPrefixGzModelNameTransform(prefix=self.prefix)(x)


__all__ = ["ProductionGzModelNameTransform"]
