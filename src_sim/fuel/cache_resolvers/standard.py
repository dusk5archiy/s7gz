from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from ..models import FuelAssetRef
from ..settings.server import FuelServerPolicy
from .protocol import CacheResolverProtocol


@dataclass(kw_only=True, frozen=True)
class StandardCacheResolver(CacheResolverProtocol):
    fuel_cache_dir: Path
    server_policy: FuelServerPolicy
    marker_glob: str = "*.sdf"

    def asset_root(self, *, asset: FuelAssetRef) -> Path:
        aliases = {s.lower() for s in self.server_policy.known_servers}
        server = (
            self.server_policy.canonical_server
            if asset.server.lower() in aliases
            else asset.server
        )
        return (
            self.fuel_cache_dir
            / server.lower()
            / unquote(asset.owner).lower()
            / asset.asset_kind
            / unquote(asset.name).lower()
        )

    def resolve(self, *, asset: FuelAssetRef) -> Path | None:
        root = self.asset_root(asset=asset)
        if not root.is_dir():
            return None
        versions = [
            p
            for p in root.iterdir()
            if p.is_dir() and p.name.isdigit() and any(p.glob(self.marker_glob))
        ]
        return max(versions, key=lambda p: int(p.name), default=None)
