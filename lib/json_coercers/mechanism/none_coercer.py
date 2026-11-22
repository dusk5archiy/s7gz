from __future__ import annotations

from dataclasses import dataclass

from lib.coercers.models import CoerceResult
from lib.coercers.protocol import CoercerProtocol


@dataclass(kw_only=True, frozen=True)
class NoneCoercer(CoercerProtocol):
    def __call__(self, *, value, dtype):
        if dtype is not type(None) and dtype is not None:
            return None

        if value is None:
            return CoerceResult(value=None)

        raise TypeError(
            {
                "value": value,
                "expected_type": str(type(None)),
                "got_type": str(type(value)),
            }
        )


__all__ = ["NoneCoercer"]
