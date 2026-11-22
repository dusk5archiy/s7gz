from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import get_type_hints

from ..models import ValidateResult
from ..protocol import StrictValidatorProtocol, ValidatorProtocol


@dataclass(kw_only=True, frozen=True)
class DataclassValidator(ValidatorProtocol):
    inner_validator: StrictValidatorProtocol

    def __call__(self, *, value, dtype):
        if not isinstance(dtype, type) or not is_dataclass(dtype):
            return None

        if not isinstance(value, dtype):
            raise TypeError(
                {
                    "value": value,
                    "expected_type": str(dtype),
                    "got_type": str(type(value)),
                }
            )

        type_hints = get_type_hints(dtype, include_extras=True)
        for definition in fields(dtype):
            if not definition.init:
                continue
            field_dtype = type_hints.get(definition.name, definition.type)
            field_value = getattr(value, definition.name)
            self.inner_validator(value=field_value, dtype=field_dtype)

        return ValidateResult()


__all__ = ["DataclassValidator"]
