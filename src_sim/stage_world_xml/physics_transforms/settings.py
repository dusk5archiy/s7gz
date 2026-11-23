from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from s7dcls import Ge, Gt, StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX

PREFIX = SIM_ENV_PREFIX + "PHYSICS__"


@dataclass(frozen=True, kw_only=True)
class Settings:
    """Gazebo physics engine and simulation step configuration."""

    enabled: bool = True
    """Override the world `<physics>` block during SDF patching."""
    engine_name: str = "4ms"
    """Identifier name attribute for the SDF `<physics>` element."""
    engine_type: Literal["dart", "ode", "bullet"] = "dart"
    """Physics solver backend."""
    max_step_size: Annotated[float, Gt(limit=0.0)] = 0.004
    """Maximum physics integration step size in seconds."""
    real_time_factor: Annotated[float, Ge(limit=0.0)] = 1.0
    """Target simulation speed relative to wall-clock time (0 for as fast as possible)."""
    collision_detector: Literal["bullet", "ode"] = "bullet"
    """Collision detection backend used by the physics engine."""

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(prefix=PREFIX),
        ).build()()
