from __future__ import annotations

from dataclasses import dataclass
from typing import get_args, get_origin

from ..models import ValidateResult
from ..protocol import StrictValidatorProtocol, ValidatorProtocol


@dataclass(kw_only=True, frozen=True)
class ListValidator(ValidatorProtocol):
    inner_validator: StrictValidatorProtocol

    def __call__(self, *, value, dtype):
        if dtype is not list and get_origin(dtype) is not list:
            return None

        if not isinstance(value, list):
            raise TypeError(
                {
                    "value": value,
                    "expected_type": str(list),
                    "got_type": str(type(value)),
                }
            )

        if get_origin(dtype) is None:
            return ValidateResult()

        elem_type = get_args(dtype)[0]
        for item in value:
            self.inner_validator(value=item, dtype=elem_type)

        return ValidateResult()


__all__ = ["ListValidator"]
