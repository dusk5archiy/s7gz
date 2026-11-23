from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import FunctionProtocol, TransformProtocol

from src_sim.settings.resource import ResourceSettings

from ..asset_ensurers.production import ProductionAssetEnsurer
from ..models import FuelAssetRef
from ..uri_rules.production import ProductionFuelUriRule
from ..uri_rules.protocol import FuelUriRuleProtocol
from .scaffold import ScaffoldFuelUriLocalizer


@dataclass(kw_only=True, frozen=True)
class ProductionFuelUriLocalizer(TransformProtocol[str]):
    s_resource: ResourceSettings = field(default_factory=ResourceSettings.build)
    rule: FuelUriRuleProtocol = field(default_factory=ProductionFuelUriRule)
    asset_ensurer: FunctionProtocol[FuelAssetRef, Path] = field(
        default_factory=ProductionAssetEnsurer
    )

    def __call__(self, x: str) -> str:
        def _resolve_asset(ref: FuelAssetRef) -> Path | None:
            return self.asset_ensurer(ref)

        return ScaffoldFuelUriLocalizer(
            rule=self.rule,
            asset_dir_resolver=_resolve_asset,
            s_resource=self.s_resource,
        )(x)
