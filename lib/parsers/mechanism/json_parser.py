from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from lib.json_coercers.protocol import StrictJsonCoercerProtocol

from ..models import ParseResult
from ..protocol import ParserProtocol


@dataclass(kw_only=True, frozen=True)
class JsonParser(ParserProtocol):
    json_coercer: StrictJsonCoercerProtocol

    def can_handle(self, *, dtype: Any) -> bool:
        return self.json_coercer.can_handle(dtype=dtype)

    def __call__(self, *, string: str, dtype: Any) -> ParseResult | None:
        if not self.can_handle(dtype=dtype):
            return None

        try:
            parsed = json.loads(string)
        except json.JSONDecodeError as e:
            raise ValueError(
                {"string": string, "expected_type": str(dtype), "e": e}
            ) from e

        _result = self.json_coercer(value=parsed, dtype=dtype)
        return ParseResult(value=_result.value)


__all__ = ["JsonParser"]
