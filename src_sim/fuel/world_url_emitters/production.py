from __future__ import annotations

from dataclasses import dataclass, field

from s7dcls import EmitterProtocol

from ..settings.download import DownloadSettings
from ..settings.server import ServerSettings
from ..settings.world import WorldSettings
from .scaffold import ScaffoldWorldUrlEmitter
from .settings import Settings
from .standard import JsonCatalogLoader, StandardFuelWorldUrlBuilder


@dataclass(kw_only=True, frozen=True)
class ProductionWorldUrlEmitter(EmitterProtocol[str | None]):
    settings: Settings = field(default_factory=Settings.build)
    s_world: WorldSettings = field(default_factory=WorldSettings.build)
    s_server: ServerSettings = field(default_factory=ServerSettings.build)
    s_download: DownloadSettings = field(default_factory=DownloadSettings.build)

    def __call__(self) -> str | None:
        return ScaffoldWorldUrlEmitter(
            world_name=self.s_world.world_name,
            world_url=self.s_world.world_url,
            catalog_loader=JsonCatalogLoader(catalog_file=self.settings.catalog_file),
            fallback_url_builder=StandardFuelWorldUrlBuilder(
                canonical_server=self.s_server.canonical_server,
                default_owner=self.settings.default_owner,
                scheme=self.s_download.scheme,
            ),
        )()
