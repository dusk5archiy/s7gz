from __future__ import annotations

from typing import Any, Protocol

from lib.coercers.models import CoerceResult
from lib.coercers.protocol import CoercerProtocol


class JsonContainerCoercerProtocol(Protocol):
    def __call__(
        self,
        *,
        value: Any,
        dtype: Any,
        coercer: CoercerProtocol | None,
    ) -> CoerceResult | None: ...
