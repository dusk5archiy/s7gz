from __future__ import annotations

from typing import Any, Protocol

from .models import ValidateResult


class ValidatorProtocol(Protocol):
    def __call__(self, *, value: Any, dtype: Any) -> ValidateResult | None: ...


class StrictValidatorProtocol(ValidatorProtocol, Protocol):
    def __call__(self, *, value: Any, dtype: Any) -> ValidateResult: ...
