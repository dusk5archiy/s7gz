from __future__ import annotations

from dataclasses import dataclass, field

from src_common.subprocess_launchers.production import ProductionSubprocessLauncher
from src_sim.settings.resource import ResourceSettings
from src_sim.stage_run.gz_command_emitters.production import ProductionGzCommandEmitter
from src_sim.stage_run.gz_command_emitters.protocol import GzCommandEmitterProtocol

from .protocol import LauncherProtocol
from .scaffold import ScaffoldSimLauncher


class ProductionSimLauncher(LauncherProtocol):
    @dataclass(kw_only=True, frozen=True)
    class Args:
        gz_command_emitter: GzCommandEmitterProtocol = field(
            default_factory=ProductionGzCommandEmitter,
        )

        s_resource: ResourceSettings = field(default_factory=ResourceSettings.build)

        def build(self):
            return ProductionSimLauncher(self)

    def __init__(self, args: Args):
        self.args = args
        resource = args.s_resource
        subprogress_launcher = ProductionSubprocessLauncher(
            command_emitter=args.gz_command_emitter
        )
        self.parent = ScaffoldSimLauncher(
            runtime_dirs=(
                resource.source_worlds_dir,
                resource.patched_worlds_dir,
                resource.fuel_cache_dir,
                resource.generated_models_dir,
            ),
            subprogress_launcher=subprogress_launcher,
        )

    def __call__(self):
        return self.parent()
