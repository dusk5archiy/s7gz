from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..models import FuelAssetRef
from .protocol import (
    AssetDownloaderProtocol,
    ManifestDownloaderProtocol,
    ManifestFetcherProtocol,
)


@dataclass(kw_only=True, frozen=True)
class ScaffoldAssetDownloader(AssetDownloaderProtocol):
    servers: tuple[str, ...]
    manifest_fetcher: ManifestFetcherProtocol
    manifest_downloader: ManifestDownloaderProtocol

    def __call__(self, *, asset: FuelAssetRef, asset_root: Path) -> Path:
        candidates = tuple(dict.fromkeys([*self.servers, asset.server]))
        errors: list[Exception] = []
        for server in candidates:
            try:
                manifest = self.manifest_fetcher(server=server, asset=asset)
                return self.manifest_downloader(
                    server=server,
                    asset=asset,
                    manifest=manifest,
                    asset_root=asset_root,
                )
            except Exception as exc:
                errors.append(exc)

        raise RuntimeError(
            f"Failed to download Fuel asset {asset.owner}/{asset.asset_kind}/{asset.name} "
            f"from servers {candidates}"
        ) from (errors[-1] if errors else None)
