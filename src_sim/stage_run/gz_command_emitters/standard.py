from __future__ import annotations

import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from s7dcls import EmitterProtocol
from src_common.subprocess_launchers.models import SubprocessCommand

from .protocol import GzCommandEmitterProtocol


def _merge_unique_paths(*path_groups: Iterable[str]) -> list[str]:
    flat_paths = (path for group in path_groups for path in group if path)
    return list(dict.fromkeys(flat_paths))


@dataclass(kw_only=True, frozen=True)
class StandardGzCommandBuilder(GzCommandEmitterProtocol):
    fuel_cache_dir: Path
    resource_paths: Sequence[Path]
    headless: bool
    auto_run: bool = True
    gz_executable: str = "gz"
    base_env: None | Mapping[str, str] = None
    world_sdf_emitter: EmitterProtocol[Path]
    gui_config_file_emitter: EmitterProtocol[Path | None]

    def __post_init__(self) -> None:
        if not self.gz_executable:
            raise ValueError({"gz_executable": self.gz_executable})

    def _ensure_required_files_exist(
        self, *, world_sdf: Path, gui_config_file: Path | None
    ) -> None:
        if not world_sdf.is_file():
            raise FileNotFoundError({"world_sdf": world_sdf})

        _gui_config_is_required_and_missing = (
            not self.headless
            and gui_config_file is not None
            and not gui_config_file.is_file()
        )
        if _gui_config_is_required_and_missing:
            raise FileNotFoundError({"gui_config_file": gui_config_file})

    def _build_cmd(self, *, world_sdf: Path, gui_config_file: Path | None) -> list[str]:
        cmd = [self.gz_executable, "sim"]

        if self.auto_run:
            cmd.append("-r")

        if self.headless:
            cmd.append("-s")
        elif gui_config_file is not None:
            cmd.extend(["--gui-config", str(gui_config_file)])

        cmd.append(str(world_sdf))
        return cmd

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ if self.base_env is None else self.base_env)
        env["GZ_FUEL_CACHE_PATH"] = str(self.fuel_cache_dir)

        existing_resource_paths = env.get("GZ_SIM_RESOURCE_PATH", "").split(os.pathsep)
        configured_resource_paths = (str(path) for path in self.resource_paths)
        merged_resource_paths = _merge_unique_paths(
            configured_resource_paths,
            existing_resource_paths,
        )

        if merged_resource_paths:
            env["GZ_SIM_RESOURCE_PATH"] = os.pathsep.join(merged_resource_paths)

        return env

    def __call__(self):
        world_sdf = self.world_sdf_emitter()
        gui_config_file = self.gui_config_file_emitter()
        self._ensure_required_files_exist(
            world_sdf=world_sdf, gui_config_file=gui_config_file
        )

        return SubprocessCommand(
            cmd=self._build_cmd(world_sdf=world_sdf, gui_config_file=gui_config_file),
            env=self._build_env(),
        )
