from __future__ import annotations

from dataclasses import dataclass

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX


@dataclass(frozen=True, kw_only=True)
class Settings:
    enabled: bool = True
    filename: str = "dummy"

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(
                prefix=SIM_ENV_PREFIX + "STRIP_PLUGINS__"
            ),
        ).build()()
