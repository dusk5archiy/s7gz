from __future__ import annotations

from dataclasses import dataclass

from .protocol import StringTransformProtocol


@dataclass(kw_only=True, frozen=True)
class LeftStripNCharsTransform(StringTransformProtocol):
    n: int

    def __call__(self, *, string):
        return string[self.n :]


@dataclass(kw_only=True, frozen=True)
class PrefixRemover(StringTransformProtocol):
    prefix: str

    def __call__(self, *, string):
        return string.lstrip(self.prefix)


@dataclass(kw_only=True, frozen=True)
class UpperTransform(StringTransformProtocol):
    def __call__(self, *, string):
        return string.upper()
