from __future__ import annotations

from dataclasses import dataclass

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX

PREFIX = SIM_ENV_PREFIX + "FUEL__"


@dataclass(kw_only=True, frozen=True)
class WorldSettings:
    """Target Gazebo Fuel world selection."""

    world_name: str | None = None
    """Local or cached world name (falls back to empty world when null)."""
    world_url: str | None = None
    """Full Fuel world URL to download and resolve dependencies from."""

    @classmethod
    def build(cls) -> WorldSettings:
        return StandardDataclassFetcher.Args(
            datacls=WorldSettings,
            dict_emitter=StandardShellDictFetcher(prefix=PREFIX),
        ).build()()


Settings = WorldSettings
