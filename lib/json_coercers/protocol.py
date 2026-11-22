from __future__ import annotations

from typing import Any, Protocol

from lib.coercers.protocol import CoercerProtocol, StrictCoercerProtocol


class JsonCoercerProtocol(CoercerProtocol, Protocol):
    def can_handle(self, *, dtype: Any) -> bool: ...


class StrictJsonCoercerProtocol(
    StrictCoercerProtocol, JsonCoercerProtocol, Protocol
): ...
