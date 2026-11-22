from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..models import FuelAssetRef
from ..settings.download import DownloadSettings
from ..settings.server import ServerSettings
from .protocol import AssetDownloaderProtocol
from .scaffold import ScaffoldAssetDownloader
from .standard import (
    StandardHttpEndpoint,
    StandardManifestDownloader,
    StandardManifestFetcher,
)


@dataclass(kw_only=True, frozen=True)
class ProductionAssetDownloader(AssetDownloaderProtocol):
    s_download: DownloadSettings = field(default_factory=DownloadSettings.build)
    s_server: ServerSettings = field(default_factory=ServerSettings.build)

    def __call__(self, *, asset: FuelAssetRef, asset_root: Path) -> Path:
        endpoint = StandardHttpEndpoint(scheme=self.s_download.scheme)
        return ScaffoldAssetDownloader(
            servers=self.s_server.server_policy.download_servers,
            manifest_fetcher=StandardManifestFetcher(
                endpoint=endpoint,
                timeout_s=self.s_download.timeout_s,
            ),
            manifest_downloader=StandardManifestDownloader(
                endpoint=endpoint,
                max_workers=self.s_download.max_workers,
                timeout_s=self.s_download.timeout_s,
            ),
        )(asset=asset, asset_root=asset_root)
