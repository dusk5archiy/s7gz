from dataclasses import dataclass

from ..models import ParseResult
from ..protocol import ParserProtocol


@dataclass(kw_only=True, frozen=True)
class TypeCallParser(ParserProtocol):
    datatype: type

    def __call__(self, *, string, dtype):
        if dtype is not self.datatype:
            return None
        try:
            return ParseResult(value=self.datatype(string))
        except ValueError as e:
            raise ValueError(
                f"Unsupported value '{string}' for type '{dtype}': {e}"
            ) from e


__all__ = ["TypeCallParser"]
