from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX


@dataclass(frozen=True, kw_only=True)
class Settings:
    enabled: bool = True
    render_engine: Literal["ogre2", "ogre"] = "ogre2"

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(
                prefix=SIM_ENV_PREFIX + "SENSORS_PLUGIN__"
            ),
        ).build()()
