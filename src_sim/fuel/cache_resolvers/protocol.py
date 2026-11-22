from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..models import FuelAssetRef


class CacheResolverProtocol(Protocol):
    def asset_root(self, *, asset: FuelAssetRef) -> Path: ...

    def resolve(self, *, asset: FuelAssetRef) -> Path | None: ...
