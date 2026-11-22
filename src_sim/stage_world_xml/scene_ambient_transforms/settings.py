from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from s7dcls import (
    IntervalRangeValueChecker,
    StandardDataclassFetcher,
    StandardShellDictFetcher,
)

from src_common.conventions.env_prefix import SIM_ENV_PREFIX


@dataclass(frozen=True, kw_only=True)
class Settings:
    enabled: bool = True

    _ambient: tuple[
        Annotated[float, IntervalRangeValueChecker.sigmoid()],
        Annotated[float, IntervalRangeValueChecker.sigmoid()],
        Annotated[float, IntervalRangeValueChecker.sigmoid()],
        Annotated[float, IntervalRangeValueChecker.sigmoid()],
    ] = (0.0, 0.0, 0.0, 1.0)

    _uniform: None | Annotated[float, IntervalRangeValueChecker.sigmoid()] = None

    @property
    def ambient(self):
        if self._uniform is not None:
            return (self._uniform, self._uniform, self._uniform, 1.0)

        return self._ambient

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(prefix=SIM_ENV_PREFIX + "AMBIENT__"),
        ).build()()
