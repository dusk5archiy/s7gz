from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ..models import FuelUriMatch
from ..settings.server import ServerSettings
from .protocol import FuelUriRuleProtocol
from .standard import StandardFuelUriRule


@dataclass(kw_only=True, frozen=True)
class ProductionFuelUriRule(FuelUriRuleProtocol):
    s_server: ServerSettings = field(default_factory=ServerSettings.build)

    def _delegate(self) -> StandardFuelUriRule:
        return StandardFuelUriRule(
            known_servers=self.s_server.server_policy.known_servers
        )

    def find_all(self, *, text: str) -> list[FuelUriMatch]:
        return self._delegate().find_all(text=text)

    def replace_all(
        self, *, text: str, rewrite: Callable[[FuelUriMatch], str | None]
    ) -> str:
        return self._delegate().replace_all(text=text, rewrite=rewrite)
