from __future__ import annotations

from dataclasses import dataclass

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX

PREFIX = SIM_ENV_PREFIX + "SYSTEM_PLUGINS__"

WORLD_SYSTEM_PLUGINS: tuple[tuple[str, str], ...] = (
    ("gz-sim-physics-system", "gz::sim::systems::Physics"),
    ("gz-sim-user-commands-system", "gz::sim::systems::UserCommands"),
    ("gz-sim-scene-broadcaster-system", "gz::sim::systems::SceneBroadcaster"),
    ("gz-sim-contact-system", "gz::sim::systems::Contact"),
    ("gz-sim-imu-system", "gz::sim::systems::Imu"),
    ("gz-sim-air-pressure-system", "gz::sim::systems::AirPressure"),
    ("gz-sim-magnetometer-system", "gz::sim::systems::Magnetometer"),
    ("gz-sim-navsat-system", "gz::sim::systems::NavSat"),
)


@dataclass(frozen=True, kw_only=True)
class Settings:
    """Core Gazebo system plugins injected into the world SDF."""

    enabled: bool = True
    """Ensure required Gazebo system plugins are present in the world SDF."""
    plugins: tuple[tuple[str, str], ...] = WORLD_SYSTEM_PLUGINS
    """List of `(plugin_filename, plugin_cpp_class)` pairs to inject."""

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(prefix=PREFIX),
        ).build()()
