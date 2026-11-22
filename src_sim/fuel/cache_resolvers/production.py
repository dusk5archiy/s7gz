from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src_sim.settings.resource import ResourceSettings

from ..models import FuelAssetRef
from ..settings.server import ServerSettings
from .protocol import CacheResolverProtocol
from .settings import Settings
from .standard import StandardCacheResolver


@dataclass(kw_only=True, frozen=True)
class ProductionCacheResolver(CacheResolverProtocol):
    settings: Settings = field(default_factory=Settings.build)
    s_server: ServerSettings = field(default_factory=ServerSettings.build)
    s_resource: ResourceSettings = field(default_factory=ResourceSettings.build)

    def _delegate(self) -> StandardCacheResolver:
        return StandardCacheResolver(
            fuel_cache_dir=self.s_resource.fuel_cache_dir,
            server_policy=self.s_server.server_policy,
            marker_glob=self.settings.marker_glob,
        )

    def asset_root(self, *, asset: FuelAssetRef) -> Path:
        return self._delegate().asset_root(asset=asset)

    def resolve(self, *, asset: FuelAssetRef) -> Path | None:
        return self._delegate().resolve(asset=asset)
