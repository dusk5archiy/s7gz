from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..models import FuelAssetId


class AssetDirRewriterProtocol(Protocol):
    def __call__(
        self,
        *,
        asset_dir: Path,
        resolved: dict[FuelAssetId, Path],
    ) -> None: ...
