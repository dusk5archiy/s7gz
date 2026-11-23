from __future__ import annotations

from dataclasses import dataclass

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX


@dataclass(kw_only=True, frozen=True)
class Settings:
    repo_url: str = "https://github.com/PX4/PX4-gazebo-models.git"
    ref: str = "main"

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(
                prefix=SIM_ENV_PREFIX + "PX4_MODELS__"
            ),
        ).build()()
