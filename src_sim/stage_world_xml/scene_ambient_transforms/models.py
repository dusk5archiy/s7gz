from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from s7dcls import IntervalRangeValueChecker

UnitFloat = Annotated[float, IntervalRangeValueChecker.sigmoid()]


@dataclass(frozen=True, kw_only=True)
class AmbientColor:
    """Normalized RGBA ambient light color in [0.0, 1.0]."""

    red: UnitFloat = 0.0
    """Red channel intensity [0.0, 1.0]."""
    green: UnitFloat = 0.0
    """Green channel intensity [0.0, 1.0]."""
    blue: UnitFloat = 0.0
    """Blue channel intensity [0.0, 1.0]."""
    alpha: UnitFloat = 1.0
    """Alpha opacity channel [0.0, 1.0]."""
