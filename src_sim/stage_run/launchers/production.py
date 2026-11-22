from __future__ import annotations

from dataclasses import dataclass, field

from src_sim.settings.resource import ResourceSettings
from src_sim.stage_run.command_launchers.production import ProductionCommandLauncher
from src_sim.stage_run.launchers.scaffold import PrepareFolderLauncher

from .protocol import LauncherProtocol


@dataclass(kw_only=True, frozen=True)
class ProductionSimLauncher(LauncherProtocol):
    s_resource: ResourceSettings = field(default_factory=ResourceSettings.build)
    command_launcher: LauncherProtocol = field(
        default_factory=ProductionCommandLauncher
    )

    def __call__(self):
        resource = self.s_resource
        runtime_dirs = (
            resource.source_worlds_dir,
            resource.patched_worlds_dir,
            resource.fuel_cache_dir,
            resource.generated_models_dir,
        )
        return PrepareFolderLauncher(
            runtime_dirs=runtime_dirs,
            next_launcher=self.command_launcher,
        )()
