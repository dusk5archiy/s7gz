from __future__ import annotations

from dataclasses import dataclass

from .protocol import GzModelNameTransformProtocol


@dataclass(kw_only=True, frozen=True)
class ScaffoldPrefixGzModelNameTransform(GzModelNameTransformProtocol):
    """Map a vehicle namespace (`str`) to its Gazebo model name (`str`) using a fixed prefix."""

    prefix: str

    def __call__(self, x: str) -> str:
        cleaned = x.strip()
        if not cleaned:
            raise ValueError("Vehicle namespace must be non-empty")
        return f"{self.prefix}{cleaned}"


__all__ = ["ScaffoldPrefixGzModelNameTransform"]
