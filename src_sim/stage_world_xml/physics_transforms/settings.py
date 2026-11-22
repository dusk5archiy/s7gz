from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from s7dcls import Ge, Gt, StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX


@dataclass(frozen=True, kw_only=True)
class Settings:
    enabled: bool = True
    engine_name: str = "4ms"
    engine_type: Literal["dart", "ode", "bullet"] = "dart"
    max_step_size: Annotated[float, Gt(limit=0.0)] = 0.004
    real_time_factor: Annotated[float, Ge(limit=0.0)] = 1.0
    collision_detector: Literal["bullet", "ode"] = "bullet"

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(prefix=SIM_ENV_PREFIX + "PHYSICS__"),
        ).build()()
