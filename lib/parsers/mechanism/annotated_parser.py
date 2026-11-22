from dataclasses import dataclass
from typing import Annotated, get_args, get_origin

from lib.value_checkers.protocol import ValueCheckerProtocol

from ..protocol import ParserProtocol, StrictParserProtocol


@dataclass(kw_only=True, frozen=True)
class AnnotatedParser(ParserProtocol):
    inner_converter: StrictParserProtocol

    def __call__(self, *, string, dtype):
        if get_origin(dtype) is not Annotated:
            return None

        base_type, *extras = get_args(dtype)
        result = self.inner_converter(string=string, dtype=base_type)

        for extra in extras:
            if isinstance(extra, ValueCheckerProtocol):
                extra(result.value)

        return result


__all__ = ["AnnotatedParser"]
