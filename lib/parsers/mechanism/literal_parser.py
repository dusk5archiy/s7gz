from dataclasses import dataclass
from typing import Literal, get_args, get_origin

from ..models import ParseResult
from ..protocol import ParserProtocol, StrictParserProtocol


@dataclass(kw_only=True, frozen=True)
class LiteralParser(ParserProtocol):
    """Parse string inputs strictly matching one of the choices in `Literal[...]`."""

    inner_converter: StrictParserProtocol

    def __call__(self, *, string, dtype):
        if get_origin(dtype) is not Literal:
            return None

        allowed = get_args(dtype)
        for choice in allowed:
            try:
                result = self.inner_converter(string=string, dtype=type(choice))
            except (ValueError, TypeError):
                continue
            if result.value == choice and type(result.value) is type(choice):
                return ParseResult(value=choice)

        raise ValueError({"string": string, "expected_type": str(dtype)})


__all__ = ["LiteralParser"]
