from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from lib.dataclass_fetchers.standard import StandardDataclassFetcher
from lib.dict_fetchers.standard import StandardShellDictFetcher
from lib.value_checkers.mechanism.interval_range import IntervalRangeValueChecker
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
