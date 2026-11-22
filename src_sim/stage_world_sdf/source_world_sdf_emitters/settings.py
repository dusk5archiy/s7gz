from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lib.dataclass_fetchers.standard import StandardDataclassFetcher
from lib.dict_fetchers.standard import StandardShellDictFetcher
from src_common.conventions.env_prefix import SIM_ENV_PREFIX
from src_sim.settings.arg import ArgSettings


@dataclass(kw_only=True, frozen=True)
class Settings:
    _world_file: None | Path = None
    s_arg: ArgSettings = field(default_factory=ArgSettings.build)

    @property
    def world_file(self) -> None | Path:
        if self._world_file is None:
            return None

        return self._world_file.expanduser().resolve()

    @property
    def empty_world_file(self):
        return (
            Path("/opt/ros")
            / self.s_arg.ros_distro
            / "opt/gz_sim_vendor/share/gz/gz-sim/worlds/empty.sdf"
        )

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(prefix=SIM_ENV_PREFIX),
        ).build()()
