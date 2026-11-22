from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..models import FuelAssetRef, FuelManifest


class ManifestFetcherProtocol(Protocol):
    def __call__(self, *, server: str, asset: FuelAssetRef) -> FuelManifest: ...


class ManifestDownloaderProtocol(Protocol):
    def __call__(
        self,
        *,
        server: str,
        asset: FuelAssetRef,
        manifest: FuelManifest,
        asset_root: Path,
    ) -> Path: ...


class AssetDownloaderProtocol(Protocol):
    def __call__(self, *, asset: FuelAssetRef, asset_root: Path) -> Path: ...
