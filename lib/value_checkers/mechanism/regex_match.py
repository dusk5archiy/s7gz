from __future__ import annotations

import re
from dataclasses import dataclass

from ..protocol import ValueCheckerProtocol


@dataclass(kw_only=True, frozen=True)
class RegexMatch(ValueCheckerProtocol):
    pattern: str

    def __call__(self, value) -> None:
        if not isinstance(value, str):
            raise TypeError({"value": value, "expected_type": str(str)})
        if re.fullmatch(self.pattern, value) is None:
            raise ValueError({"value": value, "pattern": self.pattern})


__all__ = ["RegexMatch"]
