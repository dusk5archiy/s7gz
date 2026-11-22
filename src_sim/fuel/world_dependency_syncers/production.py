from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import FunctionProtocol, SwallowerProtocol

from ..asset_dir_rewriters.production import ProductionAssetDirRewriter
from ..asset_dir_rewriters.protocol import AssetDirRewriterProtocol
from ..asset_ensurers.production import ProductionAssetEnsurer
from ..fuel_uris import FuelUriExtractor
from ..models import FuelAssetRef
from ..settings.download import DownloadSettings
from ..uri_rules.production import ProductionFuelUriRule
from ..uri_rules.protocol import FuelUriRuleProtocol
from .scaffold import ScaffoldWorldDependencySyncer
from .standard import BfsDependencyClosure, ThreadedBatchAssetEnsurer


@dataclass(kw_only=True, frozen=True)
class ProductionWorldDependencySyncer(SwallowerProtocol[Path]):
    s_download: DownloadSettings = field(default_factory=DownloadSettings.build)
    uri_rule: FuelUriRuleProtocol = field(default_factory=ProductionFuelUriRule)
    asset_ensurer: FunctionProtocol[FuelAssetRef, Path] = field(
        default_factory=ProductionAssetEnsurer
    )
    asset_rewriter: AssetDirRewriterProtocol = field(
        default_factory=ProductionAssetDirRewriter
    )

    def __call__(self, x: Path) -> None:
        return ScaffoldWorldDependencySyncer(
            dependency_closure=BfsDependencyClosure(
                batch_ensurer=ThreadedBatchAssetEnsurer(
                    asset_ensurer=self.asset_ensurer,
                    max_workers=min(4, self.s_download.max_workers),
                ),
                ref_extractor=FuelUriExtractor(rule=self.uri_rule),
            ),
            asset_rewriter=self.asset_rewriter,
        )(x)
