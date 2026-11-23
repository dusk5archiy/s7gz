from __future__ import annotations

from dataclasses import dataclass

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX

PREFIX = SIM_ENV_PREFIX + "STRIP_PLUGINS__"


@dataclass(frozen=True, kw_only=True)
class Settings:
    """Strip unwanted plugins from downloaded source world SDF files."""

    enabled: bool = True
    """Enable plugin stripping on the source world SDF."""
    filename: str = "dummy"
    """Plugin filename pattern to strip from the world SDF."""

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(prefix=PREFIX),
        ).build()()
