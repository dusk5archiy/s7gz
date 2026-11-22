from __future__ import annotations

from dataclasses import dataclass

from ..models import ValidateResult
from ..protocol import ValidatorProtocol


@dataclass(kw_only=True, frozen=True)
class TypeInstanceValidator(ValidatorProtocol):
    datatype: type

    def __call__(self, *, value, dtype):
        if dtype is not self.datatype:
            return None

        if self.datatype is int:
            is_valid = isinstance(value, int) and not isinstance(value, bool)
        elif self.datatype is float:
            is_valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        else:
            is_valid = isinstance(value, self.datatype)

        if is_valid:
            return ValidateResult()

        raise TypeError(
            {
                "value": value,
                "expected_type": str(self.datatype),
                "got_type": str(type(value)),
            }
        )


__all__ = ["TypeInstanceValidator"]
