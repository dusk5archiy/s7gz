from dataclasses import dataclass

from ..models import ParseResult
from ..protocol import ParserProtocol


@dataclass(kw_only=True, frozen=True)
class BoolParser(ParserProtocol):
    trues: tuple[str, ...] = ("1", "true", "yes", "on")
    falses: tuple[str, ...] = ("0", "false", "no", "off")

    def __call__(self, *, string, dtype):
        if dtype is not bool:
            return None

        s = string.strip().lower()
        if s in self.trues:
            return ParseResult(value=True)
        if s in self.falses:
            return ParseResult(value=False)
        raise ValueError(f"Unsupported value '{string}' for type '{dtype}'")


__all__ = ["BoolParser"]
