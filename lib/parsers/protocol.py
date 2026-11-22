from __future__ import annotations

from typing import Any, Protocol

from .models import ParseResult


class ParserProtocol(Protocol):
    def __call__(self, *, string: str, dtype: Any) -> ParseResult | None: ...


class StrictParserProtocol(ParserProtocol, Protocol):
    def __call__(self, *, string: str, dtype: Any) -> ParseResult: ...
