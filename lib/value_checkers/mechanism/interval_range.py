from __future__ import annotations

from dataclasses import dataclass

from ..protocol import ValueCheckerProtocol


@dataclass(kw_only=True, frozen=True)
class IntervalRangeValueChecker(ValueCheckerProtocol):
    min: float
    max: float

    def __call__(self, value):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError({"value": value, "expected_type": "int | float"})

        if not self.min <= value <= self.max:
            raise ValueError(
                {"expected_min": self.min, "expected_max": self.max, "value": value}
            )

    @classmethod
    def sigmoid(cls):
        return cls(min=0.0, max=1.0)


__all__ = ["IntervalRangeValueChecker"]
