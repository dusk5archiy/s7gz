from __future__ import annotations

from dataclasses import dataclass

from ..protocol import ValueCheckerProtocol


@dataclass(kw_only=True, frozen=True)
class NonEmptyStr(ValueCheckerProtocol):
    strip: bool = True

    def __call__(self, value) -> None:
        if not isinstance(value, str):
            raise TypeError({"value": value, "expected_type": str(str)})
        target = value.strip() if self.strip else value
        if not target:
            raise ValueError({"value": value, "reason": "must not be empty"})


__all__ = ["NonEmptyStr"]
