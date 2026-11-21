from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(kw_only=True, frozen=True)
class CoerceResult:
    value: Any
