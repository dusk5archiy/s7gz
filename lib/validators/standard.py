from __future__ import annotations

from pathlib import Path

from .mechanism import (
    AnnotatedValidator,
    AnyValidator,
    DataclassValidator,
    DictValidator,
    ListValidator,
    LiteralValidator,
    NoneValidator,
    TupleValidator,
    TypeInstanceValidator,
    UnionValidator,
)
from .protocol import StrictValidatorProtocol, ValidatorProtocol


class StandardValidator(StrictValidatorProtocol):
    def __init__(self) -> None:
        self.validators: tuple[ValidatorProtocol, ...] = (
            AnyValidator(),
            AnnotatedValidator(inner_validator=self),
            UnionValidator(inner_validator=self),
            LiteralValidator(),
            NoneValidator(),
            TypeInstanceValidator(datatype=bool),
            TypeInstanceValidator(datatype=int),
            TypeInstanceValidator(datatype=float),
            TypeInstanceValidator(datatype=str),
            TypeInstanceValidator(datatype=Path),
            ListValidator(inner_validator=self),
            DictValidator(inner_validator=self),
            TupleValidator(inner_validator=self),
            DataclassValidator(inner_validator=self),
        )

    def __call__(self, *, value, dtype):
        for validator in self.validators:
            result = validator(value=value, dtype=dtype)
            if result is not None:
                return result

        raise TypeError({"value": value, "expected_type": str(dtype)})


__all__ = ["StandardValidator"]
