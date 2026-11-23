from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import FunctionProtocol

from src_sim.settings.resource import ResourceSettings

from .scaffold import ScaffoldPx4ModelEnsurer
from .settings import Settings
from .standard import GitSparsePx4ModelDownloader


@dataclass(kw_only=True, frozen=True)
class ProductionPx4ModelEnsurer(FunctionProtocol[str, Path]):
    settings: Settings = field(default_factory=Settings.build)
    s_resource: ResourceSettings = field(default_factory=ResourceSettings.build)

    def __call__(self, x: str) -> Path:
        cache_dir = self.s_resource.cache_dir / "px4_gazebo_models"
        return ScaffoldPx4ModelEnsurer(
            cache_dir=cache_dir,
            downloader=GitSparsePx4ModelDownloader(
                cache_dir=cache_dir,
                repo_url=self.settings.repo_url,
                ref=self.settings.ref,
            ),
        )(x)
