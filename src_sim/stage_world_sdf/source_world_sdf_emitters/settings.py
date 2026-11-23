from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX
from src_common.conventions.ui_property import ui_property
from src_sim.settings.arg import ArgSettings
from src_sim.settings.asset_ref import AssetRef, resolve_world_asset_path

PREFIX = SIM_ENV_PREFIX


@dataclass(kw_only=True, frozen=True)
class Settings:
    """Active world SDF selection (catalog-managed or custom path) and fallback empty world."""

    active_world: None | AssetRef = None
    """Selected world SDF: either a catalog relative path (under source_worlds/) or a direct path."""
    s_arg: ArgSettings = field(default_factory=ArgSettings.build, init=False)

    @ui_property
    @property
    def world_file(self) -> None | Path:
        """Resolved source world SDF path from active_world, if configured."""
        if self.active_world is None:
            return None
        return resolve_world_asset_path(self.active_world, prefer_patched=False)

    @ui_property
    @property
    def empty_world_file(self) -> Path:
        """Default Gazebo empty.sdf world path resolved from __ARG__ROS_DISTRO."""
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
