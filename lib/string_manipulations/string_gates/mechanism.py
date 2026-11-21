from __future__ import annotations

from dataclasses import dataclass

from .protocol import StringGateProtocol


@dataclass(kw_only=True, frozen=True)
class NoCasePrefixGate(StringGateProtocol):
    prefix: str

    def __call__(self, *, string):
        _normalized_string = string.upper()
        _normalized_prefix = self.prefix.upper()
        if _normalized_string.startswith(_normalized_prefix):
            return string[len(self.prefix) :]

        return None
