from __future__ import annotations

from dataclasses import dataclass

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX


@dataclass(frozen=True, kw_only=True)
class Settings:
    enabled: bool = True
    magnetic_field: tuple[float, float, float] = (6e-06, 2.3e-05, -4.2e-05)

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(
                prefix=SIM_ENV_PREFIX + "MAGNETIC_FIELD__"
            ),
        ).build()()
