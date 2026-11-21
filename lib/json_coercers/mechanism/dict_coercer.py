from __future__ import annotations

from dataclasses import dataclass
from typing import get_args, get_origin

from lib.coercers.models import CoerceResult

from ..protocol import JsonContainerCoercerProtocol


@dataclass(kw_only=True, frozen=True)
class DictCoercer(JsonContainerCoercerProtocol):
    def __call__(self, *, value, dtype, coercer):
        if dtype is not dict and get_origin(dtype) is not dict:
            return None

        if coercer is None:
            return CoerceResult(value=None)

        if not isinstance(value, dict):
            raise TypeError(f"Expected JSON object, got {type(value).__name__}")

        if get_origin(dtype) is None:
            return CoerceResult(value=dict(value))

        key_type, val_type = get_args(dtype)
        _results = {}
        for k, v in value.items():
            _key_result = coercer(value=k, dtype=key_type)
            if _key_result is None:
                raise TypeError

            _value_result = coercer(value=v, dtype=val_type)
            if _value_result is None:
                raise TypeError

            _results[_key_result.value] = _value_result.value

        return CoerceResult(value=_results)


__all__ = ["DictCoercer"]
