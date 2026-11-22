from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from s7dcls import FunctionProtocol

from ..fs import atomic_path


@dataclass(kw_only=True, frozen=True)
class ScaffoldWorldSdfExporter(FunctionProtocol[Path, Path]):
    sdf_locator: FunctionProtocol[Path, Path]
    world_sdf_out: Path

    def __call__(self, x: Path) -> Path:
        if not self.world_sdf_out.is_file():
            source_sdf = self.sdf_locator(x)
            with atomic_path(self.world_sdf_out) as tmp_path:
                shutil.copy2(source_sdf, tmp_path)
        return self.world_sdf_out
