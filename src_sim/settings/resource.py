from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from s7dcls import StandardDataclassFetcher
from s7dcls import StandardShellDictFetcher
from src_common.conventions.env_prefix import SIM_ENV_PREFIX


@dataclass(kw_only=True, frozen=True)
class ResourceSettings:
    _runtime_dir: Path = Path("runtime")
    _fuel_cache_dir: None | Path = None
    _generated_models_dir: None | Path = None
    _source_worlds_dir: None | Path = None
    _patched_worlds_dir: None | Path = None

    @property
    def runtime_dir(self) -> Path:
        return self._runtime_dir.expanduser().resolve()

    @property
    def fuel_cache_dir(self):
        if self._fuel_cache_dir is not None:
            return self._fuel_cache_dir.expanduser().resolve()
        return (self._runtime_dir / "fuel_cache").expanduser().resolve()

    @property
    def generated_models_dir(self) -> Path:
        if self._generated_models_dir is not None:
            return self._generated_models_dir.expanduser().resolve()
        return (self._runtime_dir / "generated_models").expanduser().resolve()

    @property
    def source_worlds_dir(self) -> Path:
        if self._source_worlds_dir is not None:
            return self._source_worlds_dir.expanduser().resolve()
        return (self._runtime_dir / "source_worlds").expanduser().resolve()

    @property
    def patched_worlds_dir(self) -> Path:
        if self._patched_worlds_dir is not None:
            return self._patched_worlds_dir.expanduser().resolve()
        return (self._runtime_dir / "patched_worlds").expanduser().resolve()

    @classmethod
    def build(cls) -> ResourceSettings:
        return StandardDataclassFetcher.Args(
            datacls=ResourceSettings,
            dict_emitter=StandardShellDictFetcher(prefix=SIM_ENV_PREFIX),
        ).build()()
