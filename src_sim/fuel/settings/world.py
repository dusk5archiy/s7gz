from __future__ import annotations

from dataclasses import dataclass

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX


@dataclass(kw_only=True, frozen=True)
class WorldSettings:
    world_name: str | None = None
    world_url: str | None = None

    @classmethod
    def build(cls) -> WorldSettings:
        return StandardDataclassFetcher.Args(
            datacls=WorldSettings,
            dict_emitter=StandardShellDictFetcher(prefix=SIM_ENV_PREFIX + "FUEL__"),
        ).build()()
