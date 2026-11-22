from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import FunctionProtocol

from ..asset_downloaders.production import ProductionAssetDownloader
from ..asset_downloaders.protocol import AssetDownloaderProtocol
from ..cache_resolvers.production import ProductionCacheResolver
from ..cache_resolvers.protocol import CacheResolverProtocol
from ..models import FuelAssetRef
from .scaffold import ScaffoldAssetEnsurer


@dataclass(kw_only=True, frozen=True)
class ProductionAssetEnsurer(FunctionProtocol[FuelAssetRef, Path]):
    cache_resolver: CacheResolverProtocol = field(
        default_factory=ProductionCacheResolver
    )
    downloader: AssetDownloaderProtocol = field(
        default_factory=ProductionAssetDownloader
    )

    def __call__(self, x: FuelAssetRef) -> Path:
        return ScaffoldAssetEnsurer(
            cache_resolver=self.cache_resolver,
            downloader=self.downloader,
        )(x)
