from dataclasses import dataclass
from types import UnionType
from typing import Union, get_args, get_origin

from ..protocol import ParserProtocol, StrictParserProtocol


@dataclass(kw_only=True, frozen=True)
class UnionParser(ParserProtocol):
    """
    Caution: Union order matters.
    """

    inner_converter: StrictParserProtocol

    def __call__(self, *, string, dtype):
        origin = get_origin(dtype)
        if origin not in (UnionType, Union):
            return None

        args = get_args(dtype)
        errors: list[Exception] = []

        for arg in args:
            try:
                return self.inner_converter(string=string, dtype=arg)
            except (ValueError, TypeError) as e:
                errors.append(e)
                continue

        if errors:
            if any(isinstance(e, ValueError) for e in errors):
                raise ValueError(
                    {"string": string, "expected_type": str(dtype), "errors": errors}
                ) from errors[-1]
            raise TypeError(
                {"string": string, "expected_type": str(dtype), "errors": errors}
            ) from errors[-1]

        return None


__all__ = ["UnionParser"]
