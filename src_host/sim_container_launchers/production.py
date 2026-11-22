from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

from s7dcls import EmitterProtocol
from src_common.subprocess_launchers.models import SubprocessCommand
from src_common.subprocess_launchers.standard import StandardSubprocessLauncher
from src_host.settings.common import CommonSettings
from src_host.settings.sim_container import SimContainerSettings
from src_host.sim_docker_command_emitters.production import (
    ProductionSimDockerCommandEmitter,
)


@dataclass(kw_only=True, frozen=True)
class ProductionSimContainerLauncher(EmitterProtocol[int]):
    s_common: CommonSettings = field(default_factory=CommonSettings.build)
    s_sim_container: SimContainerSettings = field(
        default_factory=SimContainerSettings.build
    )

    command_emitter: EmitterProtocol[SubprocessCommand] = field(
        default_factory=ProductionSimDockerCommandEmitter
    )

    def _prepare(self) -> None:
        s_sim_container = self.s_sim_container
        s_common = self.s_common
        s_common.runtime_dir.mkdir(parents=True, exist_ok=True)

        if s_sim_container.xhost_local:
            try:
                subprocess.run(
                    ["xhost", "+local:"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except FileNotFoundError:
                pass

        if s_sim_container.force_recreate and s_sim_container.container_name:
            subprocess.run(
                [
                    s_common.docker_executable,
                    "rm",
                    "-f",
                    s_sim_container.container_name,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

    def __call__(self) -> int:
        self._prepare()
        return StandardSubprocessLauncher(command_emitter=self.command_emitter)()
