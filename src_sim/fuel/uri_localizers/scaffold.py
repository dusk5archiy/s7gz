from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from s7dcls import FunctionProtocol, TransformProtocol

from ..models import FuelAssetRef, FuelUriMatch
from ..uri_rules.protocol import FuelUriRuleProtocol


@dataclass(kw_only=True, frozen=True)
class ScaffoldFuelUriLocalizer(TransformProtocol[str]):
    rule: FuelUriRuleProtocol
    asset_dir_resolver: FunctionProtocol[FuelAssetRef, Path | None]

    def __call__(self, x: str) -> str:
        def _rewrite(match: FuelUriMatch) -> str | None:
            version_dir = self.asset_dir_resolver(match.asset)
            if version_dir is None:
                return None
            target = version_dir / match.subpath if match.subpath else version_dir
            return f"{target.as_uri()}{match.trailing_ws}"

        return self.rule.replace_all(text=x, rewrite=_rewrite)
