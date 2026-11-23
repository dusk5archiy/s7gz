from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX
from src_common.conventions.ui_property import ui_property

PREFIX = SIM_ENV_PREFIX


@dataclass(kw_only=True, frozen=True)
class ResourceSettings:
    """Base orthogonal filesystem roots for runtime assets, worlds, and caches.

    All paths are relative to the current working directory (project root on host,
    WORKDIR /ws-s7gz inside Docker) unless explicitly overridden with an absolute path.
    """

    _runtime_dir: None | Path = None
    """Optional override for the base runtime directory (defaults to runtime)."""
    _cache_dir: None | Path = None
    """Optional override for internal sync/VCS cache directory (defaults to runtime/.cache)."""
    _source_models_dir: None | Path = None
    """Override root for raw source models grouped by provider (<dir>/<provider>/...)."""
    _patched_models_dir: None | Path = None
    """Override root for patched models grouped by provider (<dir>/<provider>/...)."""
    _source_worlds_dir: None | Path = None
    """Override root for raw source worlds grouped by provider (<dir>/<provider>/...)."""
    _patched_worlds_dir: None | Path = None
    """Override root for patched worlds grouped by provider (<dir>/<provider>/...)."""
    _generated_models_dir: None | Path = None
    """Override directory for generated per-vehicle SDF packages."""

    @ui_property
    @property
    def runtime_dir(self) -> Path:
        """Base runtime directory (relative to cwd unless overridden with an absolute path)."""
        if self._runtime_dir is not None:
            return self._runtime_dir.expanduser()
        return Path("runtime")

    @ui_property
    @property
    def cache_dir(self) -> Path:
        """Internal sync/VCS cache directory."""
        if self._cache_dir is not None:
            return self._cache_dir.expanduser()
        return self.runtime_dir / ".cache"

    @ui_property
    @property
    def source_models_dir(self) -> Path:
        """Root for raw source models (<dir>/<provider>/...)."""
        if self._source_models_dir is not None:
            return self._source_models_dir.expanduser()
        return self.runtime_dir / "source_models"

    @ui_property
    @property
    def patched_models_dir(self) -> Path:
        """Root for patched models (<dir>/<provider>/...)."""
        if self._patched_models_dir is not None:
            return self._patched_models_dir.expanduser()
        return self.runtime_dir / "patched_models"

    @ui_property
    @property
    def source_worlds_dir(self) -> Path:
        """Root for raw source worlds (<dir>/<provider>/...)."""
        if self._source_worlds_dir is not None:
            return self._source_worlds_dir.expanduser()
        return self.runtime_dir / "source_worlds"

    @ui_property
    @property
    def patched_worlds_dir(self) -> Path:
        """Root for patched worlds (<dir>/<provider>/...)."""
        if self._patched_worlds_dir is not None:
            return self._patched_worlds_dir.expanduser()
        return self.runtime_dir / "patched_worlds"

    @ui_property
    @property
    def generated_models_dir(self) -> Path:
        """Directory for generated per-vehicle SDF models."""
        if self._generated_models_dir is not None:
            return self._generated_models_dir.expanduser()
        return self.runtime_dir / "generated_models"

    def source_models_of(self, provider: str) -> Path:
        return self.source_models_dir / provider

    def patched_models_of(self, provider: str) -> Path:
        return self.patched_models_dir / provider

    def source_worlds_of(self, provider: str) -> Path:
        return self.source_worlds_dir / provider

    def patched_worlds_of(self, provider: str) -> Path:
        return self.patched_worlds_dir / provider

    @classmethod
    def build(cls) -> ResourceSettings:
        return StandardDataclassFetcher.Args(
            datacls=ResourceSettings,
            dict_emitter=StandardShellDictFetcher(prefix=PREFIX),
        ).build()()


Settings = ResourceSettings
