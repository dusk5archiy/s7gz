from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import FunctionProtocol

from ..asset_ensurers.production import ProductionAssetEnsurer
from ..models import FuelAssetRef
from .scaffold import ScaffoldWorldAssetEnsurer
from .standard import StandardFuelUrlParser


@dataclass(kw_only=True, frozen=True)
class ProductionWorldAssetEnsurer(FunctionProtocol[str, Path]):
    asset_ensurer: FunctionProtocol[FuelAssetRef, Path] = field(
        default_factory=ProductionAssetEnsurer
    )

    def __call__(self, x: str) -> Path:
        return ScaffoldWorldAssetEnsurer(
            url_parser=StandardFuelUrlParser(),
            asset_ensurer=self.asset_ensurer,
        )(x)
