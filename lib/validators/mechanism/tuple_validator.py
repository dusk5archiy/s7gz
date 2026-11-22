from __future__ import annotations

from dataclasses import dataclass
from typing import get_args, get_origin

from ..models import ValidateResult
from ..protocol import StrictValidatorProtocol, ValidatorProtocol


@dataclass(kw_only=True, frozen=True)
class TupleValidator(ValidatorProtocol):
    inner_validator: StrictValidatorProtocol

    def __call__(self, *, value, dtype):
        if dtype is not tuple and get_origin(dtype) is not tuple:
            return None

        if not isinstance(value, tuple):
            raise TypeError(
                {
                    "value": value,
                    "expected_type": str(tuple),
                    "got_type": str(type(value)),
                }
            )

        if get_origin(dtype) is None:
            return ValidateResult()

        args = get_args(dtype)
        if len(args) == 2 and args[1] is Ellipsis:
            elem_type = args[0]
            for item in value:
                self.inner_validator(value=item, dtype=elem_type)
            return ValidateResult()

        if len(args) == 1 and args[0] == ():
            if value:
                raise ValueError({"value": value, "expected_type": str(dtype)})
            return ValidateResult()

        if len(value) != len(args):
            raise ValueError({"value": value, "expected_type": str(dtype)})

        for item, arg_type in zip(value, args, strict=True):
            self.inner_validator(value=item, dtype=arg_type)

        return ValidateResult()


__all__ = ["TupleValidator"]
