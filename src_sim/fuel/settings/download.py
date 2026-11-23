from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from s7dcls import Ge, Gt, StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX

PREFIX = SIM_ENV_PREFIX + "FUEL__"


@dataclass(kw_only=True, frozen=True)
class DownloadSettings:
    """HTTP client settings for downloading Fuel worlds and model assets."""

    scheme: str = "https"
    """URL scheme used when requesting Fuel assets."""
    max_workers: Annotated[int, Ge(limit=1)] = 8
    """Maximum number of concurrent download worker threads."""
    timeout_s: Annotated[float, Gt(limit=0.0)] = 30.0
    """Per-request network timeout in seconds."""

    @classmethod
    def build(cls) -> DownloadSettings:
        return StandardDataclassFetcher.Args(
            datacls=DownloadSettings,
            dict_emitter=StandardShellDictFetcher(prefix=PREFIX),
        ).build()()


Settings = DownloadSettings
