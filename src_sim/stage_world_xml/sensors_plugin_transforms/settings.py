from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX

PREFIX = SIM_ENV_PREFIX + "SENSORS_PLUGIN__"


@dataclass(frozen=True, kw_only=True)
class Settings:
    """Gazebo Sensors system plugin configuration."""

    enabled: bool = True
    """Inject the `gz::sim::systems::Sensors` plugin into the world SDF."""
    render_engine: Literal["ogre2", "ogre"] = "ogre2"
    """Rendering engine used by camera and LiDAR sensors."""

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(prefix=PREFIX),
        ).build()()
