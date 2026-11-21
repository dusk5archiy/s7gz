from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lib.dataclass_fetchers.standard import StandardDataclassFetcher
from lib.dict_fetchers.standard import StandardShellDictFetcher


@dataclass(kw_only=True, frozen=True)
class SimContainerSettings:
    image_name: str
    container_name: str
    user_name: str

    sim_ws_dir: Path = Path("/ws-s7gz")
    detach: bool = False
    gpu: bool = True
    shm_size: str = "2g"
    xhost_local: bool = True
    force_recreate: bool = True
    env_prefix: str = "__SIM__"
    entrypoint: Path = Path("/usr/local/bin/entrypoint.sh")

    @classmethod
    def build(cls) -> SimContainerSettings:
        return StandardDataclassFetcher.Args(
            dtype=SimContainerSettings,
            dict_fetchers=[StandardShellDictFetcher(prefix="__HOST_SIM__")],
        ).build()()
