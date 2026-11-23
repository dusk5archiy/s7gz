from __future__ import annotations

from dataclasses import dataclass, field

from s7dcls import (
    StandardDataclassFetcher,
    StandardShellDictFetcher,
)

from src_common.conventions.env_prefix import SIM_ENV_PREFIX
from src_common.conventions.ui_property import ui_property

from .models import AmbientColor, UnitFloat

PREFIX = SIM_ENV_PREFIX + "AMBIENT__"


@dataclass(frozen=True, kw_only=True)
class Settings:
    """World scene ambient lighting override."""

    enabled: bool = True
    """Apply `<scene><ambient>` color to the patched world SDF."""

    _ambient: AmbientColor = field(default_factory=AmbientColor)
    """RGBA ambient color channels."""

    _uniform: None | UnitFloat = None
    """Optional uniform grayscale intensity [0.0, 1.0] overriding RGB with alpha=1.0."""

    @ui_property
    @property
    def ambient(self) -> AmbientColor:
        """Effective RGBA ambient color after applying _uniform override if set."""
        if self._uniform is not None:
            return AmbientColor(
                red=self._uniform,
                green=self._uniform,
                blue=self._uniform,
                alpha=1.0,
            )

        return self._ambient

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(prefix=PREFIX),
        ).build()()
