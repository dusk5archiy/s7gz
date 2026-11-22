from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from s7dcls import FunctionProtocol

from ..models import FuelAssetRef


@dataclass(kw_only=True, frozen=True)
class ScaffoldWorldAssetEnsurer(FunctionProtocol[str, Path]):
    url_parser: FunctionProtocol[str, FuelAssetRef]
    asset_ensurer: FunctionProtocol[FuelAssetRef, Path]

    def __call__(self, x: str) -> Path:
        asset = self.url_parser(x)
        return self.asset_ensurer(asset)
