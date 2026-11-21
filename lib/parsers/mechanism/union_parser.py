from dataclasses import dataclass
from types import UnionType
from typing import Union, get_args, get_origin

from ..protocol import ParserProtocol


@dataclass(kw_only=True, frozen=True)
class UnionParser(ParserProtocol):
    """
    Caution: Union order matters.
    """

    inner_converter: ParserProtocol

    def __call__(self, *, string, dtype):
        origin = get_origin(dtype)
        if origin not in (UnionType, Union):
            return None

        args = get_args(dtype)
        errors: list[str] = []

        for arg in args:
            try:
                result = self.inner_converter(string=string, dtype=arg)
            except (ValueError, TypeError) as e:
                errors.append(str(e))
                continue

            if result is not None:
                return result

        if errors:
            raise ValueError(
                f"Unsupported value '{string}' for type '{dtype}': {errors}"
            )

        return None


__all__ = ["UnionParser"]
