from __future__ import annotations

from dataclasses import dataclass
from typing import get_args, get_origin

from lib.coercers.models import CoerceResult

from ..protocol import JsonContainerCoercerProtocol


@dataclass(kw_only=True, frozen=True)
class TupleCoercer(JsonContainerCoercerProtocol):
    def __call__(self, *, value, dtype, coercer):
        if dtype is not tuple and get_origin(dtype) is not tuple:
            return None

        if coercer is None:
            return CoerceResult(value=None)

        if not isinstance(value, list):
            raise TypeError(f"Expected JSON array, got {type(value).__name__}")

        if get_origin(dtype) is None:
            return CoerceResult(value=tuple(value))

        args = get_args(dtype)
        if len(args) == 2 and args[1] is Ellipsis:
            _results = []
            for item in value:
                _result = coercer(value=item, dtype=args[0])
                if _result is None:
                    raise TypeError

                _results.append(_result.value)

            return CoerceResult(value=tuple(_results))

        if len(args) == 1 and args[0] == ():
            if value:
                raise ValueError(f"Expected empty tuple, got {len(value)} item(s)")
            return CoerceResult(value=())
        if len(value) != len(args):
            raise ValueError(f"Expected tuple of length {len(args)}, got {len(value)}")

        _results = []
        for item, arg_type in zip(value, args, strict=True):
            _result = coercer(value=item, dtype=arg_type)
            if _result is None:
                raise TypeError

            _results.append(_result.value)

        return CoerceResult(value=tuple(_results))


__all__ = ["TupleCoercer"]
