from __future__ import annotations

from dataclasses import dataclass, field

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX

from .models import MagneticField

PREFIX = SIM_ENV_PREFIX + "MAGNETIC_FIELD__"


@dataclass(frozen=True, kw_only=True)
class Settings:
    """Ensure `<magnetic_field>` is present in the world SDF for magnetometers."""

    enabled: bool = True
    """Insert `<magnetic_field>` when missing from the source world SDF."""
    magnetic_field: MagneticField = field(default_factory=MagneticField)
    """Default Earth magnetic field vector (Tesla, ENU) to inject."""

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(prefix=PREFIX),
        ).build()()
