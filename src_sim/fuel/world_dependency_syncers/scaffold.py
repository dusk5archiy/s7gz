from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from s7dcls import FunctionProtocol, SwallowerProtocol

from ..asset_dir_rewriters.protocol import AssetDirRewriterProtocol
from ..models import FuelAssetId
from ..progress import emit_fuel_progress


@dataclass(kw_only=True, frozen=True)
class ScaffoldWorldDependencySyncer(SwallowerProtocol[Path]):
    dependency_closure: FunctionProtocol[str, dict[FuelAssetId, Path]]
    asset_rewriter: AssetDirRewriterProtocol

    def __call__(self, x: Path) -> None:
        sdf_text = x.read_text(encoding="utf-8")
        resolved = self.dependency_closure(sdf_text)
        if resolved:
            emit_fuel_progress(
                f"Rewriting URIs in {len(resolved)} dependency asset(s)...",
                kind="rewrite",
            )
        for version_dir in resolved.values():
            self.asset_rewriter(asset_dir=version_dir, resolved=resolved)
