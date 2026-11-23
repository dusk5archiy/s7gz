from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import FunctionProtocol, TransformProtocol

from src_sim.settings.resource import ResourceSettings

from ..models import FuelAssetRef, FuelUriMatch
from ..uri_rules.protocol import FuelUriRuleProtocol


@dataclass(kw_only=True, frozen=True)
class ScaffoldFuelUriLocalizer(TransformProtocol[str]):
    rule: FuelUriRuleProtocol
    asset_dir_resolver: FunctionProtocol[FuelAssetRef, Path | None]
    s_resource: ResourceSettings = field(default_factory=ResourceSettings.build)

    def __call__(self, x: str) -> str:
        runtime_root = self.s_resource.runtime_dir.resolve()
        source_models_root = self.s_resource.source_models_dir.resolve()
        patched_models_root = self.s_resource.patched_models_dir.resolve()

        def _rewrite(match: FuelUriMatch) -> str | None:
            version_dir = self.asset_dir_resolver(match.asset)
            if version_dir is None:
                return None
            resolved_dir = version_dir.resolve()
            if resolved_dir.is_relative_to(source_models_root):
                rel_from_source = resolved_dir.relative_to(source_models_root).as_posix()
                if match.subpath:
                    sub = match.subpath.lstrip("/")
                    return f"model://source_models/{rel_from_source}/{sub}{match.trailing_ws}"
                if match.asset.asset_kind == "models":
                    return f"model://patched_models/{rel_from_source}{match.trailing_ws}"
                return f"model://source_models/{rel_from_source}{match.trailing_ws}"

            if resolved_dir.is_relative_to(patched_models_root):
                rel_from_patched = resolved_dir.relative_to(patched_models_root).as_posix()
                if match.subpath:
                    sub = match.subpath.lstrip("/")
                    return f"model://patched_models/{rel_from_patched}/{sub}{match.trailing_ws}"
                return f"model://patched_models/{rel_from_patched}{match.trailing_ws}"

            target = resolved_dir / match.subpath if match.subpath else resolved_dir
            if target.is_relative_to(runtime_root):
                rel = target.relative_to(runtime_root).as_posix()
                return f"model://{rel}{match.trailing_ws}"
            return f"file://{target.as_posix()}{match.trailing_ws}"

        return self.rule.replace_all(text=x, rewrite=_rewrite)
