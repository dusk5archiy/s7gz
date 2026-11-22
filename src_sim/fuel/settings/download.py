from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from s7dcls import Ge, Gt, StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX


@dataclass(kw_only=True, frozen=True)
class DownloadSettings:
    scheme: str = "https"
    max_workers: Annotated[int, Ge(limit=1)] = 8
    timeout_s: Annotated[float, Gt(limit=0.0)] = 30.0

    @classmethod
    def build(cls) -> DownloadSettings:
        return StandardDataclassFetcher.Args(
            datacls=DownloadSettings,
            dict_emitter=StandardShellDictFetcher(prefix=SIM_ENV_PREFIX + "FUEL__"),
        ).build()()
