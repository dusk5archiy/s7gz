from __future__ import annotations

from dataclasses import dataclass

from s7dcls import StandardDataclassFetcher
from s7dcls import StandardShellDictFetcher


@dataclass(kw_only=True, frozen=True)
class ArgSettings:
    ros_distro: str

    @classmethod
    def build(cls) -> ArgSettings:
        return StandardDataclassFetcher.Args(
            datacls=ArgSettings,
            dict_emitter=StandardShellDictFetcher(prefix="__ARG__"),
        ).build()()
