from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX


@dataclass(kw_only=True, frozen=True)
class Settings:
    default_owner: str = "OpenRobotics"
    _catalog_file: Path | None = None

    @property
    def catalog_file(self) -> Path:
        if self._catalog_file is not None:
            return self._catalog_file.expanduser().resolve()
        return Path(__file__).with_name("worlds_catalog.json").resolve()

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(prefix=SIM_ENV_PREFIX + "FUEL__"),
        ).build()()
