from typing import Any, Protocol

from .models import CoerceResult


class CoercerProtocol(Protocol):
    def __call__(self, *, value: Any, dtype: Any) -> CoerceResult | None: ...
