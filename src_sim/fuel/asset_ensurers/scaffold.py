from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from s7dcls import FunctionProtocol

from ..asset_downloaders.protocol import AssetDownloaderProtocol
from ..cache_resolvers.protocol import CacheResolverProtocol
from ..models import FuelAssetRef


@dataclass(kw_only=True, frozen=True)
class ScaffoldAssetEnsurer(FunctionProtocol[FuelAssetRef, Path]):
    cache_resolver: CacheResolverProtocol
    downloader: AssetDownloaderProtocol

    def __call__(self, x: FuelAssetRef) -> Path:
        cached = self.cache_resolver.resolve(asset=x)
        if cached is not None:
            return cached
        asset_root = self.cache_resolver.asset_root(asset=x)
        return self.downloader(asset=x, asset_root=asset_root)
