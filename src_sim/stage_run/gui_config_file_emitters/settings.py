from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from s7dcls import StandardDataclassFetcher
from s7dcls import StandardShellDictFetcher
from src_common.conventions.env_prefix import SIM_ENV_PREFIX


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
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(prefix=SIM_ENV_PREFIX),
        ).build()()
