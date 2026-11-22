from __future__ import annotations

from dataclasses import dataclass

from lib.type_emitters.protocol import FunctionProtocol


@dataclass(kw_only=True, frozen=True)
class NoCasePrefixGate(FunctionProtocol[str, str | None]):
    prefix: str

    def __call__(self, string):
        _normalized_string = string.upper()
        _normalized_prefix = self.prefix.upper()
        if _normalized_string.startswith(_normalized_prefix):
            return string[len(self.prefix) :]

        return None
