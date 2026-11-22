from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lib.coercers.models import CoerceResult
from lib.coercers.protocol import CoercerProtocol, StrictCoercerProtocol
from lib.dataclass_hydrators.protocol import DataclassHydratorProtocol
from lib.dataclass_hydrators.scaffold import ScaffoldDataclassHydrator

from .mechanism import (
    AnnotatedCoercer,
    DataclassCoercer,
    DictCoercer,
    ListCoercer,
    LiteralCoercer,
    NoneCoercer,
    PathCoercer,
    TupleCoercer,
    TypeInstanceCoercer,
    UnionCoercer,
)
from .protocol import JsonCoercerProtocol, StrictJsonCoercerProtocol


class StandardJsonCoercer(StrictJsonCoercerProtocol):
    @dataclass(kw_only=True, frozen=True)
    class Args:
        fallback_coercer: StrictCoercerProtocol | None = None
        dataclass_hydrator: DataclassHydratorProtocol | None = None

        def build(self) -> StandardJsonCoercer:
            return StandardJsonCoercer(self)

    def __init__(self, args: Args) -> None:
        self.fallback_coercer = args.fallback_coercer

        dataclass_hydrator = args.dataclass_hydrator or ScaffoldDataclassHydrator()

        self.container_coercers: tuple[JsonCoercerProtocol, ...] = (
            DictCoercer(inner_coercer=self),
            ListCoercer(inner_coercer=self),
            TupleCoercer(inner_coercer=self),
            DataclassCoercer(
                inner_coercer=self,
                dataclass_hydrator=dataclass_hydrator,
            ),
        )
        self.coercers: tuple[CoercerProtocol, ...] = (
            AnnotatedCoercer(inner_coercer=self),
            UnionCoercer(inner_coercer=self),
            LiteralCoercer(),
            *self.container_coercers,
            NoneCoercer(),
            TypeInstanceCoercer(datatype=bool),
            TypeInstanceCoercer(datatype=int),
            TypeInstanceCoercer(datatype=float),
            TypeInstanceCoercer(datatype=str),
            PathCoercer(),
        )

    def can_handle(self, *, dtype: Any) -> bool:
        return any(
            coercer.can_handle(dtype=dtype) for coercer in self.container_coercers
        )

    def __call__(self, *, value: Any, dtype: Any) -> CoerceResult:
        if dtype is Any:
            return CoerceResult(value=value)

        for coercer in self.coercers:
            _result = coercer(value=value, dtype=dtype)
            if _result is not None:
                return _result

        if self.fallback_coercer is not None:
            return self.fallback_coercer(value=value, dtype=dtype)

        raise TypeError({"value": value, "expected_type": str(dtype)})


__all__ = ["StandardJsonCoercer"]
