from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from lib.dict_fetchers.standard import StandardJsonDictFetcher, StandardShellDictFetcher
from lib.type_emitters.protocol import TypeEmitterProtocol
from src_common.docker_command_emitters.models import VolumeMount
from src_common.docker_command_emitters.standard import StandardDockerCommandEmitter
from src_common.subprocess_launchers.models import SubprocessCommand
from src_host.settings.common import CommonSettings
from src_host.settings.sim_container import SimContainerSettings


@dataclass(kw_only=True, frozen=True)
class ProductionSimDockerCommandEmitter(TypeEmitterProtocol[SubprocessCommand]):
    s_sim_container: SimContainerSettings = field(
        default_factory=SimContainerSettings.build
    )
    s_common: CommonSettings = field(default_factory=CommonSettings.build)

    def _build_env(self) -> dict[str, str]:
        s_sim_container = self.s_sim_container
        env: dict[str, str] = {
            "NVIDIA_DRIVER_CAPABILITIES": "all",
            "NVIDIA_VISIBLE_DEVICES": "all",
        }
        display = os.environ.get("DISPLAY")
        if display:
            env["DISPLAY"] = display

        ui_vars = StandardJsonDictFetcher(
            prefix=s_sim_container.env_prefix, file=self.s_common.ui_json_file
        )()
        shell_vars = StandardShellDictFetcher(prefix=s_sim_container.env_prefix)()

        for key, value in {**ui_vars, **shell_vars}.items():
            if value != "":
                env[f"{s_sim_container.env_prefix}{key}"] = value

        return env

    def _build_volumes(self) -> tuple[VolumeMount, ...]:
        repo = self.s_common.repo_root
        runtime = self.s_common.runtime_dir
        ws = self.s_sim_container.sim_ws_dir

        repo_mounts = (
            VolumeMount(source=repo / "lib", target=ws / "lib"),
            VolumeMount(source=repo / "src_sim", target=ws / "src_sim"),
            VolumeMount(source=repo / "src_common", target=ws / "src_common"),
        )

        return (
            *repo_mounts,
            VolumeMount(source=runtime, target=ws / "runtime"),
            VolumeMount(
                source=repo / "src_sim" / "entrypoint.sh",
                target=self.s_sim_container.entrypoint,
                mode="ro",
            ),
            VolumeMount(
                source=Path("/tmp/.X11-unix"), target=Path("/tmp/.X11-unix"), mode="rw"
            ),
        )

    def __call__(self) -> SubprocessCommand:
        s_sim_container = self.s_sim_container
        s_common = self.s_common
        return StandardDockerCommandEmitter(
            docker_executable=s_common.docker_executable,
            image=s_sim_container.image_name,
            container_name=s_sim_container.container_name,
            user=s_sim_container.user_name,
            workdir=s_sim_container.sim_ws_dir,
            network="host",
            ipc="host",
            shm_size=s_sim_container.shm_size,
            detach=s_sim_container.detach,
            init=True,
            tty=True,
            interactive=True,
            gpu=s_sim_container.gpu,
            env=self._build_env(),
            volumes=self._build_volumes(),
        )()
