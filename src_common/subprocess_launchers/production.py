from dataclasses import dataclass, field

from lib.type_emitters.protocol import TypeEmitterProtocol
from src_common.subprocess_launchers.models import SubprocessCommand

from .protocol import SubprocessLauncherProtocol
from .settings import Settings
from .standard import StandardSubprocessLauncher


@dataclass(kw_only=True, frozen=True)
class ProductionSubprocessLauncher(SubprocessLauncherProtocol):
    settings: Settings = field(default_factory=Settings.build)
    command_emitter: TypeEmitterProtocol[SubprocessCommand]

    def __call__(self):
        return StandardSubprocessLauncher(
            terminate_timeout_s=self.settings.terminate_timeout_s,
            supported_signums=self.settings.supported_signums,
            command_emitter=self.command_emitter,
        )()
