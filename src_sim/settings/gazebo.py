from __future__ import annotations

from dataclasses import dataclass

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX

PREFIX = SIM_ENV_PREFIX


@dataclass(kw_only=True, frozen=True)
class GazeboSettings:
    """Gazebo simulator launch mode."""

    headless: bool = False
    """Run Gazebo server without GUI window."""

    @classmethod
    def build(cls) -> GazeboSettings:
        return StandardDataclassFetcher.Args(
            datacls=GazeboSettings,
            dict_emitter=StandardShellDictFetcher(prefix=PREFIX),
        ).build()()


Settings = GazeboSettings
