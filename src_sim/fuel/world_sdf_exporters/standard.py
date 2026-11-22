from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from s7dcls import FunctionProtocol


@dataclass(kw_only=True, frozen=True)
class FirstSdfLocator(FunctionProtocol[Path, Path]):
    def __call__(self, x: Path) -> Path:
        top_level = sorted(x.glob("*.sdf"))
        if top_level:
            return top_level[0]
        nested = sorted(x.rglob("*.sdf"))
        if nested:
            return nested[0]
        raise FileNotFoundError(f"No .sdf world file found inside {x}")
