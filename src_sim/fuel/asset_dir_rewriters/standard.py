from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..fs import atomic_path
from ..ignition_plugin_transforms import IgnitionPluginTransform
from ..models import FuelAssetId, FuelAssetRef
from ..uri_localizers.scaffold import ScaffoldFuelUriLocalizer
from ..uri_rules.protocol import FuelUriRuleProtocol
from ..uri_rules.standard import StandardFuelUriRule
from .protocol import AssetDirRewriterProtocol
from src_sim.settings.resource import ResourceSettings

DEFAULT_TEXT_EXTENSIONS: tuple[str, ...] = (".sdf", ".config", ".dae", ".material")


@dataclass(kw_only=True, frozen=True)
class StandardAssetDirRewriter(AssetDirRewriterProtocol):
    rule: FuelUriRuleProtocol
    s_resource: ResourceSettings = field(default_factory=ResourceSettings.build)
    plugin_transform: IgnitionPluginTransform = field(
        default_factory=IgnitionPluginTransform
    )
    text_extensions: tuple[str, ...] = DEFAULT_TEXT_EXTENSIONS

    @classmethod
    def from_servers(cls, known_servers: tuple[str, ...]) -> StandardAssetDirRewriter:
        return cls(rule=StandardFuelUriRule(known_servers=known_servers))

    def __call__(
        self,
        *,
        asset_dir: Path,
        resolved: dict[FuelAssetId, Path],
    ) -> None:
        def _resolve_asset(x: FuelAssetRef) -> Path | None:
            return resolved.get(x.id)

        localizer = ScaffoldFuelUriLocalizer(
            rule=self.rule,
            asset_dir_resolver=_resolve_asset,
            s_resource=self.s_resource,
        )
        for path in sorted(asset_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in self.text_extensions:
                continue
            original = path.read_text(encoding="utf-8", errors="ignore")
            updated = self.plugin_transform(localizer(original))
            if updated != original:
                with atomic_path(path) as tmp_path:
                    tmp_path.write_text(updated, encoding="utf-8")
