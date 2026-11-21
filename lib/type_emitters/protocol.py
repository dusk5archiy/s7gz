from __future__ import annotations

from typing import Protocol


class TypeEmitterProtocol[T](Protocol):
    def __call__(self) -> T: ...
