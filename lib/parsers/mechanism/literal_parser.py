from dataclasses import dataclass
from typing import Literal, get_args, get_origin

from ..models import ParseResult
from ..protocol import ParserProtocol


@dataclass(kw_only=True, frozen=True)
class LiteralParser(ParserProtocol):
    """Parse string inputs strictly matching one of the choices in `Literal[...]`."""

    inner_converter: ParserProtocol

    def __call__(self, *, string, dtype):
        if get_origin(dtype) is not Literal:
            return None

        allowed = get_args(dtype)
        for choice in allowed:
            try:
                result = self.inner_converter(string=string, dtype=type(choice))
            except ValueError:
                continue
            if (
                result is not None
                and result.value == choice
                and type(result.value) is type(choice)
            ):
                return ParseResult(value=choice)

        raise ValueError(
            f"Unsupported value '{string}' for Literal{list(allowed)}; expected one of {allowed!r}"
        )


__all__ = ["LiteralParser"]
