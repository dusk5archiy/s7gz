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
        except (ValueError, TypeError) as e:
            raise type(e)(
                {"string": string, "expected_type": str(dtype), "e": e}
            ) from e


__all__ = ["TypeCallParser"]
