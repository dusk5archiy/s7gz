from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, get_args, get_origin

from lib.coercers.protocol import CoercerProtocol, StrictCoercerProtocol
from lib.value_checkers.protocol import ValueCheckerProtocol


@dataclass(kw_only=True, frozen=True)
class AnnotatedCoercer(CoercerProtocol):
    inner_coercer: StrictCoercerProtocol

    def __call__(self, *, value, dtype):
        if get_origin(dtype) is not Annotated:
            return None

        base_type, *extras = get_args(dtype)
        result = self.inner_coercer(value=value, dtype=base_type)

        for extra in extras:
            if isinstance(extra, ValueCheckerProtocol):
                extra(result.value)

        return result


__all__ = ["AnnotatedCoercer"]
