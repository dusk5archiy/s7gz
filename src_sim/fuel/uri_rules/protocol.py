from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from ..models import FuelUriMatch


class FuelUriRuleProtocol(Protocol):
    def find_all(self, *, text: str) -> list[FuelUriMatch]: ...

    def replace_all(
        self, *, text: str, rewrite: Callable[[FuelUriMatch], str | None]
    ) -> str: ...
