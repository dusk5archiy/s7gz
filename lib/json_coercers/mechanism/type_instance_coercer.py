from __future__ import annotations

from dataclasses import dataclass

from lib.coercers.models import CoerceResult
from lib.coercers.protocol import CoercerProtocol


@dataclass(kw_only=True, frozen=True)
class TypeInstanceCoercer(CoercerProtocol):
    datatype: type

    def __call__(self, *, value, dtype):
        if dtype is not self.datatype:
            return None

        if self.datatype is int:
            if isinstance(value, int) and not isinstance(value, bool):
                return CoerceResult(value=value)
        elif self.datatype is float:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return CoerceResult(value=float(value))
        elif isinstance(value, self.datatype):
            return CoerceResult(value=value)

        raise TypeError(
            {
                "value": value,
                "expected_type": str(self.datatype),
                "got_type": str(type(value)),
            }
        )


__all__ = ["TypeInstanceCoercer"]
