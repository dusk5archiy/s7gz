from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src_sim.fuel.settings.world import WorldSettings
from src_sim.settings.resource import ResourceSettings
from src_sim.stage_world_sdf.fuel_world_sdf_emitters.production import (
    ProductionFuelWorldSdfEmitter,
)
from src_sim.stage_world_sdf.world_sdf_emitters.production import (
    ProductionWorldSdfEmitter,
)

from ..settings_services.protocol import SettingsServiceProtocol
from .protocol import WorldScope, WorldServiceProtocol
from .scaffold import ScaffoldWorldService


@dataclass(kw_only=True, frozen=True)
class ProductionWorldService(WorldServiceProtocol):
    settings_service: SettingsServiceProtocol

    def _delegate(self) -> ScaffoldWorldService:
        return ScaffoldWorldService(
            settings_service=self.settings_service,
            resource_settings_factory=ResourceSettings.build,
            world_settings_factory=WorldSettings.build,
            fuel_world_emitter_factory=lambda: ProductionFuelWorldSdfEmitter()(),
            patched_world_emitter_factory=lambda: ProductionWorldSdfEmitter()(),
        )

    def list_worlds(self) -> dict[str, Any]:
        return self._delegate().list_worlds()

    def read_world(
        self, *, scope: WorldScope, relative_path: str
    ) -> dict[str, Any]:
        return self._delegate().read_world(
            scope=scope, relative_path=relative_path
        )

    def delete_world(
        self, *, scope: WorldScope, relative_path: str
    ) -> dict[str, Any]:
        return self._delegate().delete_world(
            scope=scope, relative_path=relative_path
        )

    def download_world(
        self,
        *,
        world_name: str | None = None,
        world_url: str | None = None,
        select: bool = True,
    ) -> dict[str, Any]:
        return self._delegate().download_world(
            world_name=world_name, world_url=world_url, select=select
        )

    def prepare_world(self) -> dict[str, Any]:
        return self._delegate().prepare_world()

    def patch_world(self, *, relative_path: str) -> dict[str, Any]:
        return self._delegate().patch_world(relative_path=relative_path)

    def sync_provider(self, *, provider: str) -> dict[str, Any]:
        return self._delegate().sync_provider(provider=provider)


__all__ = ["ProductionWorldService"]
