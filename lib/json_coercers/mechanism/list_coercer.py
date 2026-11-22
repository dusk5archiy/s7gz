from __future__ import annotations

from dataclasses import dataclass
from typing import Any, get_args, get_origin

from lib.coercers.models import CoerceResult
from lib.coercers.protocol import StrictCoercerProtocol

from ..protocol import JsonCoercerProtocol


@dataclass(kw_only=True, frozen=True)
class ListCoercer(JsonCoercerProtocol):
    inner_coercer: StrictCoercerProtocol

    def can_handle(self, *, dtype: Any) -> bool:
        return dtype is list or get_origin(dtype) is list

    def __call__(self, *, value, dtype):
        if dtype is not list and get_origin(dtype) is not list:
            return None

        if not isinstance(value, list):
            raise TypeError(
                {
                    "value": value,
                    "expected_type": str(list),
                    "got_type": str(type(value)),
                }
            )

        if get_origin(dtype) is None:
            return CoerceResult(value=list(value))

        elem_type = get_args(dtype)[0]
        _results = [
            self.inner_coercer(value=item, dtype=elem_type).value for item in value
        ]
        return CoerceResult(value=_results)


__all__ = ["ListCoercer"]
