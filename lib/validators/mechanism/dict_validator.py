from __future__ import annotations

from dataclasses import dataclass
from typing import get_args, get_origin

from ..models import ValidateResult
from ..protocol import StrictValidatorProtocol, ValidatorProtocol


@dataclass(kw_only=True, frozen=True)
class DictValidator(ValidatorProtocol):
    inner_validator: StrictValidatorProtocol

    def __call__(self, *, value, dtype):
        if dtype is not dict and get_origin(dtype) is not dict:
            return None

        if not isinstance(value, dict):
            raise TypeError(
                {
                    "value": value,
                    "expected_type": str(dict),
                    "got_type": str(type(value)),
                }
            )

        if get_origin(dtype) is None:
            return ValidateResult()

        key_type, val_type = get_args(dtype)
        for k, v in value.items():
            self.inner_validator(value=k, dtype=key_type)
            self.inner_validator(value=v, dtype=val_type)

        return ValidateResult()


__all__ = ["DictValidator"]
