from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import TransformProtocol

from ..cache_resolvers.production import ProductionCacheResolver
from ..cache_resolvers.protocol import CacheResolverProtocol
from ..models import FuelAssetRef
from ..uri_rules.production import ProductionFuelUriRule
from ..uri_rules.protocol import FuelUriRuleProtocol
from .scaffold import ScaffoldFuelUriLocalizer


@dataclass(kw_only=True, frozen=True)
class ProductionFuelUriLocalizer(TransformProtocol[str]):
    rule: FuelUriRuleProtocol = field(default_factory=ProductionFuelUriRule)
    cache_resolver: CacheResolverProtocol = field(
        default_factory=ProductionCacheResolver
    )

    def __call__(self, x: str) -> str:
        def _resolve_asset(x: FuelAssetRef) -> Path | None:
            return self.cache_resolver.resolve(asset=x)

        return ScaffoldFuelUriLocalizer(
            rule=self.rule,
            asset_dir_resolver=_resolve_asset,
        )(x)
