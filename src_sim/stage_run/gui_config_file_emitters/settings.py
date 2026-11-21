from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lib.dataclass_fetchers.standard import StandardDataclassFetcher
from lib.dict_fetchers.standard import StandardShellDictFetcher


@dataclass(kw_only=True, frozen=True)
class Settings:
    _gui_config_enabled: bool = True
    _gui_config_file: None | Path = None

    @property
    def gui_config_file(self) -> Path | None:
        if not self._gui_config_enabled:
            return None

        if self._gui_config_file is not None:
            return self._gui_config_file.expanduser().resolve()

        return Path(__file__).with_name("gazebo_gui.config").expanduser().resolve()

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            dtype=Settings,
            dict_fetchers=[StandardShellDictFetcher(prefix="__SIM__")],
        ).build()()
