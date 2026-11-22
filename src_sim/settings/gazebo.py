from __future__ import annotations

from dataclasses import dataclass

from lib.dataclass_fetchers.standard import StandardDataclassFetcher
from lib.dict_fetchers.standard import StandardShellDictFetcher
from src_common.conventions.env_prefix import SIM_ENV_PREFIX


@dataclass(kw_only=True, frozen=True)
class GazeboSettings:
    headless: bool = False

    @classmethod
    def build(cls) -> GazeboSettings:
        return StandardDataclassFetcher.Args(
            datacls=GazeboSettings,
            dict_emitter=StandardShellDictFetcher(prefix=SIM_ENV_PREFIX),
        ).build()()
