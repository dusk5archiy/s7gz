from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lib.datacls_assigners.protocol import DataclsAssignerProtocol

from .mechanism import (
    AnnotatedParser,
    BoolParser,
    JsonParser,
    LiteralParser,
    NoneParser,
    TypeCallParser,
    UnionParser,
)
from .protocol import ParserProtocol


class InnerParser(ParserProtocol):
    @dataclass(kw_only=True, frozen=True)
    class Args:
        datacls_assigner: DataclsAssignerProtocol

        def build(self):
            return InnerParser(self)

    def __init__(self, args: Args):
        self.converters: tuple[ParserProtocol, ...] = (
            AnnotatedParser(inner_converter=self),
            UnionParser(inner_converter=self),
            LiteralParser(inner_converter=self),
            BoolParser(),
            TypeCallParser(datatype=int),
            TypeCallParser(datatype=float),
            TypeCallParser(datatype=Path),
            JsonParser.Args(
                inner_converter=self,
                datacls_assigner=args.datacls_assigner,
            ).build(),
            TypeCallParser(datatype=str),
            NoneParser(),
        )

    def __call__(self, *, string, dtype):
        for converter in self.converters:
            result = converter(string=string, dtype=dtype)
            if result is not None:
                return result

        return None


class StandardParser(ParserProtocol):
    @dataclass(kw_only=True, frozen=True)
    class Args:
        datacls_assigner: DataclsAssignerProtocol

        def build(self):
            return StandardParser(self)

    def __init__(self, args: Args):
        self.parent = InnerParser.Args(datacls_assigner=args.datacls_assigner).build()

    def __call__(self, *, string, dtype):
        _result = self.parent(string=string, dtype=dtype)

        if _result is None:
            raise TypeError({"dtype": dtype})

        return _result
