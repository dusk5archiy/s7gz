from dataclasses import dataclass, field

from s7dcls import EmitterProtocol

from src_common.subprocess_launchers.models import SubprocessCommand
from src_common.subprocess_launchers.standard import StandardSubprocessLauncher
from src_sim.stage_run.gz_command_emitters.production import ProductionGzCommandEmitter


@dataclass(kw_only=True, frozen=True)
class ProductionCommandLauncher(EmitterProtocol[int]):
    command_emitter: EmitterProtocol[SubprocessCommand] = field(
        default_factory=ProductionGzCommandEmitter
    )

    def __call__(self):
        return StandardSubprocessLauncher(
            command_emitter=self.command_emitter,
        )()
