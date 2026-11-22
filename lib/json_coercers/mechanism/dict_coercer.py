from __future__ import annotations

from dataclasses import dataclass
from typing import Any, get_args, get_origin

from lib.coercers.models import CoerceResult
from lib.coercers.protocol import StrictCoercerProtocol

from ..protocol import JsonCoercerProtocol


@dataclass(kw_only=True, frozen=True)
class DictCoercer(JsonCoercerProtocol):
    inner_coercer: StrictCoercerProtocol

    def can_handle(self, *, dtype: Any) -> bool:
        return dtype is dict or get_origin(dtype) is dict

    def __call__(self, *, value, dtype):
        if dtype is not dict and get_origin(dtype) is not dict:
            return None

        if not isinstance(value, dict):
            raise TypeError(
                {
                    "value": value,
                    "expected_dtype": str(dict),
                    "got_dtype": str(type(value)),
                }
            )

        if get_origin(dtype) is None:
            return CoerceResult(value=dict(value))

        key_type, val_type = get_args(dtype)
        _results = {}
        for k, v in value.items():
            _key_result = self.inner_coercer(value=k, dtype=key_type)
            _value_result = self.inner_coercer(value=v, dtype=val_type)
            _results[_key_result.value] = _value_result.value

        return CoerceResult(value=_results)


__all__ = ["DictCoercer"]
