from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lib.coercers.models import CoerceResult
from lib.coercers.protocol import CoercerProtocol


@dataclass(kw_only=True, frozen=True)
class PathCoercer(CoercerProtocol):
    def __call__(self, *, value, dtype):
        if dtype is not Path:
            return None

        if isinstance(value, (str, Path)):
            return CoerceResult(value=Path(value))

        raise TypeError(
            {
                "value": value,
                "expected_type": str(Path),
                "got_type": str(type(value)),
            }
        )


__all__ = ["PathCoercer"]
