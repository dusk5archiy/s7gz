from __future__ import annotations

from dataclasses import dataclass

from .models import FuelAssetId, FuelAssetRef
from .uri_rules.protocol import FuelUriRuleProtocol


@dataclass(kw_only=True, frozen=True)
class FuelUriExtractor:
    rule: FuelUriRuleProtocol

    def __call__(self, *, text: str) -> list[FuelAssetRef]:
        seen: dict[FuelAssetId, FuelAssetRef] = {}
        for match in self.rule.find_all(text=text):
            seen.setdefault(match.asset.id, match.asset)
        return list(seen.values())
