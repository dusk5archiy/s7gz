from collections.abc import Sequence
from dataclasses import dataclass

from ..models import ParseResult
from ..protocol import ParserProtocol


@dataclass(kw_only=True, frozen=True)
class NoneParser(ParserProtocol):
    values: Sequence[str] = ("", "none", "null")

    def __call__(self, *, string, dtype):
        if dtype is not type(None) and dtype is not None:
            return None
        s = string.strip().lower()
        if s in self.values:
            return ParseResult(value=None)

        raise ValueError({"string": string, "expected_type": str(dtype)})


__all__ = ["NoneParser"]
