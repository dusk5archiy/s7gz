from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lib.coercers.models import CoerceResult
from lib.coercers.protocol import StrictCoercerProtocol
from lib.dataclass_hydrators.protocol import DataclassHydratorProtocol
from lib.json_coercers.standard import StandardJsonCoercer

from .mechanism import (
    AnnotatedParser,
    BoolParser,
    JsonParser,
    LiteralParser,
    NoneParser,
    TypeCallParser,
    UnionParser,
)
from .protocol import ParserProtocol, StrictParserProtocol


def _to_parser_string(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


@dataclass(kw_only=True, frozen=True)
class _ParserFallbackCoercer(StrictCoercerProtocol):
    inner_converter: StrictParserProtocol

    def __call__(self, *, value: Any, dtype: Any) -> CoerceResult:
        as_string = _to_parser_string(value)
        _parse_result = self.inner_converter(string=as_string, dtype=dtype)
        return CoerceResult(value=_parse_result.value)


class StandardParser(StrictParserProtocol):
    @dataclass(kw_only=True, frozen=True)
    class Args:
        dataclass_hydrator: DataclassHydratorProtocol | None = None

        def build(self):
            return StandardParser(self)

    def __init__(self, args: Args):
        json_coercer = StandardJsonCoercer.Args(
            fallback_coercer=_ParserFallbackCoercer(inner_converter=self),
            dataclass_hydrator=args.dataclass_hydrator,
        ).build()

        self.converters: tuple[ParserProtocol, ...] = (
            AnnotatedParser(inner_converter=self),
            UnionParser(inner_converter=self),
            LiteralParser(inner_converter=self),
            BoolParser(),
            TypeCallParser(datatype=int),
            TypeCallParser(datatype=float),
            TypeCallParser(datatype=Path),
            JsonParser(json_coercer=json_coercer),
            TypeCallParser(datatype=str),
            NoneParser(),
        )

    def __call__(self, *, string, dtype):
        for converter in self.converters:
            result = converter(string=string, dtype=dtype)
            if result is not None:
                return result

        raise TypeError({"string": string, "expected_dtype": str(dtype)})


__all__ = ["StandardParser"]
