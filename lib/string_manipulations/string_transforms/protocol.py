from __future__ import annotations

from typing import Protocol


class StringTransformProtocol(Protocol):
    def __call__(self, *, string: str) -> str: ...
