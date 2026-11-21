from __future__ import annotations

from typing import Protocol


class StringGateProtocol(Protocol):
    def __call__(self, *, string: str) -> str | None: ...
