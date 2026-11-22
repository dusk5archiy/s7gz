from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from s7dcls import StandardDataclassFetcher
from s7dcls import StandardShellDictFetcher


@dataclass(kw_only=True, frozen=True)
class CommonSettings:
    docker_executable: str = "docker"

    _repo_root: Path = Path(".")
    _runtime_dir: None | Path = None
    _ui_json_file: None | Path = None

    @property
    def repo_root(self) -> Path:
        return self._repo_root.expanduser().resolve()

    @property
    def runtime_dir(self) -> Path:
        if self._runtime_dir is not None:
            return self._runtime_dir.expanduser().resolve()

        return self.repo_root / "runtime"

    @property
    def ui_json_file(self) -> Path:
        if self._ui_json_file is not None:
            return self._ui_json_file.expanduser().resolve()

        return self.runtime_dir / ".sim.ui.json"

    @classmethod
    def build(cls) -> CommonSettings:
        return StandardDataclassFetcher.Args(
            datacls=CommonSettings,
            dict_emitter=StandardShellDictFetcher(prefix="__HOST__"),
        ).build()()
