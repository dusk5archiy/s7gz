from __future__ import annotations

from dataclasses import dataclass
from typing import get_args, get_origin

from lib.coercers.models import CoerceResult

from ..protocol import JsonContainerCoercerProtocol


@dataclass(kw_only=True, frozen=True)
class ListCoercer(JsonContainerCoercerProtocol):
    def __call__(self, *, value, dtype, coercer):
        if dtype is not list and get_origin(dtype) is not list:
            return None

        if coercer is None:
            return CoerceResult(value=None)

        if not isinstance(value, list):
            raise TypeError(f"Expected JSON array, got {type(value).__name__}")

        if get_origin(dtype) is None:
            return CoerceResult(value=list(value))

        elem_type = get_args(dtype)[0]
        _results = []
        for item in value:
            _result = coercer(value=item, dtype=elem_type)
            if _result is None:
                raise TypeError

            _results.append(_result.value)

        return CoerceResult(value=_results)


__all__ = ["ListCoercer"]
