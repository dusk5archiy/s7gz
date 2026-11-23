from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src_sim.settings.resource import ResourceSettings

from ..models import FuelAssetId
from ..uri_rules.production import ProductionFuelUriRule
from ..uri_rules.protocol import FuelUriRuleProtocol
from .protocol import AssetDirRewriterProtocol
from .standard import StandardAssetDirRewriter


@dataclass(kw_only=True, frozen=True)
class ProductionAssetDirRewriter(AssetDirRewriterProtocol):
    s_resource: ResourceSettings = field(default_factory=ResourceSettings.build)
    rule: FuelUriRuleProtocol = field(default_factory=ProductionFuelUriRule)

    def __call__(
        self,
        *,
        asset_dir: Path,
        resolved: dict[FuelAssetId, Path],
    ) -> None:
        return StandardAssetDirRewriter(rule=self.rule, s_resource=self.s_resource)(
            asset_dir=asset_dir, resolved=resolved
        )
