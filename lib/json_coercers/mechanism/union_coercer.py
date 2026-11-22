from __future__ import annotations

from dataclasses import dataclass
from types import UnionType
from typing import Union, get_args, get_origin

from lib.coercers.protocol import CoercerProtocol, StrictCoercerProtocol


@dataclass(kw_only=True, frozen=True)
class UnionCoercer(CoercerProtocol):
    inner_coercer: StrictCoercerProtocol

    def __call__(self, *, value, dtype):
        origin = get_origin(dtype)
        if origin not in (UnionType, Union):
            return None

        args = get_args(dtype)
        errors: list[Exception] = []

        for arg in args:
            try:
                return self.inner_coercer(value=value, dtype=arg)
            except (ValueError, TypeError) as e:
                errors.append(e)
                continue

        if errors:
            if any(isinstance(e, ValueError) for e in errors):
                raise ValueError(
                    {"value": value, "expected_type": str(dtype), "errors": errors}
                ) from errors[-1]
            raise TypeError(
                {"value": value, "expected_type": str(dtype), "errors": errors}
            ) from errors[-1]

        return None


__all__ = ["UnionCoercer"]
