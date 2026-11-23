from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from s7dcls import FunctionProtocol

from ..asset_downloaders.protocol import AssetDownloaderProtocol
from ..cache_integrity import find_missing_asset_files
from ..cache_resolvers.protocol import CacheResolverProtocol
from ..models import FuelAssetRef
from ..progress import emit_fuel_progress


@dataclass(kw_only=True, frozen=True)
class ScaffoldAssetEnsurer(FunctionProtocol[FuelAssetRef, Path]):
    cache_resolver: CacheResolverProtocol
    downloader: AssetDownloaderProtocol

    def __call__(self, x: FuelAssetRef) -> Path:
        cached = self.cache_resolver.resolve(asset=x)
        if cached is not None:
            missing = find_missing_asset_files(cached)
            if not missing:
                return cached
            emit_fuel_progress(
                f"Repairing incomplete cache for {x.owner}/{x.name} ({len(missing)} missing)...",
                kind="repair",
            )
            shutil.rmtree(cached, ignore_errors=True)
        asset_root = self.cache_resolver.asset_root(asset=x)
        return self.downloader(asset=x, asset_root=asset_root)
