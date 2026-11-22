from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args, get_origin

from lib.coercers.models import CoerceResult
from lib.coercers.protocol import CoercerProtocol


@dataclass(kw_only=True, frozen=True)
class LiteralCoercer(CoercerProtocol):
    def __call__(self, *, value, dtype):
        if get_origin(dtype) is not Literal:
            return None

        allowed = get_args(dtype)
        for choice in allowed:
            if value == choice and type(value) is type(choice):
                return CoerceResult(value=choice)

        raise ValueError({"value": value, "expected_type": str(dtype)})


__all__ = ["LiteralCoercer"]
