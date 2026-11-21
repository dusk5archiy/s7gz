from dataclasses import dataclass
from typing import Annotated, get_args, get_origin

from ..protocol import ParserProtocol


@dataclass(kw_only=True, frozen=True)
class AnnotatedParser(ParserProtocol):
    inner_converter: ParserProtocol

    def __call__(self, *, string, dtype):
        if get_origin(dtype) is not Annotated:
            return None

        base_type, *extras = get_args(dtype)
        result = self.inner_converter(string=string, dtype=base_type)
        if result is None:
            return None

        for extra in extras:
            validator = getattr(extra, "validate", None)
            if callable(validator):
                validator(result.value)

        return result


__all__ = ["AnnotatedParser"]
