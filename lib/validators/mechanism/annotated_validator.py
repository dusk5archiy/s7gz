from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, get_args, get_origin

from lib.value_checkers.protocol import ValueCheckerProtocol

from ..protocol import StrictValidatorProtocol, ValidatorProtocol


@dataclass(kw_only=True, frozen=True)
class AnnotatedValidator(ValidatorProtocol):
    inner_validator: StrictValidatorProtocol

    def __call__(self, *, value, dtype):
        if get_origin(dtype) is not Annotated:
            return None

        base_type, *extras = get_args(dtype)
        result = self.inner_validator(value=value, dtype=base_type)

        for extra in extras:
            if isinstance(extra, ValueCheckerProtocol):
                extra(value)

        return result


__all__ = ["AnnotatedValidator"]
