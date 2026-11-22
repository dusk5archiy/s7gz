from __future__ import annotations

from dataclasses import dataclass

from ..models import ValidateResult
from ..protocol import ValidatorProtocol


@dataclass(kw_only=True, frozen=True)
class NoneValidator(ValidatorProtocol):
    def __call__(self, *, value, dtype):
        if dtype is not type(None) and dtype is not None:
            return None

        if value is None:
            return ValidateResult()

        raise TypeError(
            {"value": value, "expected_type": str(type(None)), "got_type": str(type(value))}
        )


__all__ = ["NoneValidator"]
