from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from lib.type_emitters.protocol import TypeEmitterProtocol
from src_common.subprocess_launchers.models import SubprocessCommand

from .models import VolumeMount


@dataclass(kw_only=True, frozen=True)
class StandardDockerCommandEmitter(TypeEmitterProtocol[SubprocessCommand]):
    image: str
    docker_executable: str = "docker"
    container_name: str | None = None
    user: str | None = None
    workdir: Path | str | None = None
    network: str | None = "host"
    ipc: str | None = "host"
    shm_size: str | None = None
    detach: bool = True
    remove: bool = False
    init: bool = True
    tty: bool = True
    interactive: bool = True
    gpu: bool = False
    env: Mapping[str, str] = field(default_factory=dict)
    volumes: Sequence[VolumeMount] = ()
    command: Sequence[str] = ()

    def __call__(self) -> SubprocessCommand:
        cmd: list[str] = [self.docker_executable, "run"]

        if self.detach:
            cmd.append("-d")
        if self.remove:
            cmd.append("--rm")
        if self.init:
            cmd.append("--init")
        if self.interactive:
            cmd.append("-i")
        if self.tty:
            cmd.append("-t")
        if self.container_name:
            cmd.extend(["--name", self.container_name])
        if self.user:
            cmd.extend(["--user", self.user])
        if self.workdir:
            cmd.extend(["--workdir", str(self.workdir)])
        if self.network:
            cmd.extend(["--network", self.network])
        if self.ipc:
            cmd.extend(["--ipc", self.ipc])
        if self.shm_size:
            cmd.extend(["--shm-size", self.shm_size])
        if self.gpu:
            cmd.extend(["--gpus", "all"])

        for key, value in self.env.items():
            cmd.extend(["-e", f"{key}={value}"])

        for volume in self.volumes:
            cmd.extend(["-v", volume.to_arg()])

        cmd.append(self.image)
        cmd.extend(self.command)

        return SubprocessCommand(cmd=cmd)
