from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..models import FuelUriMatch
from .protocol import FuelUriRuleProtocol


@dataclass(kw_only=True, frozen=True)
class SequenceFuelUriRule(FuelUriRuleProtocol):
    rules: Sequence[FuelUriRuleProtocol] = ()

    def find_all(self, *, text: str) -> list[FuelUriMatch]:
        matches: list[FuelUriMatch] = []
        for rule in self.rules:
            matches.extend(rule.find_all(text=text))
        return matches

    def replace_all(
        self, *, text: str, rewrite: Callable[[FuelUriMatch], str | None]
    ) -> str:
        out = text
        for rule in self.rules:
            out = rule.replace_all(text=out, rewrite=rewrite)
        return out
