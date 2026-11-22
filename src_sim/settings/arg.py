from __future__ import annotations

from dataclasses import dataclass

from lib.dataclass_fetchers.standard import StandardDataclassFetcher
from lib.dict_fetchers.standard import StandardShellDictFetcher


@dataclass(kw_only=True, frozen=True)
class ArgSettings:
    ros_distro: str

    @classmethod
    def build(cls) -> ArgSettings:
        return StandardDataclassFetcher.Args(
            datacls=ArgSettings,
            dict_emitter=StandardShellDictFetcher(prefix="__ARG__"),
        ).build()()
