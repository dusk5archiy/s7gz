from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import unquote, urlparse

from s7dcls import FunctionProtocol

from ..models import FuelAssetRef


@dataclass(kw_only=True, frozen=True)
class StandardFuelUrlParser(FunctionProtocol[str, FuelAssetRef]):
    def __call__(self, x: str) -> FuelAssetRef:
        parsed = urlparse(x.strip())
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"Invalid Fuel URL: {x!r}")
        parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
        if parts and parts[0] == "1.0":
            parts = parts[1:]
        if len(parts) < 3 or parts[1] not in ("models", "worlds"):
            raise ValueError(
                f"Expected Fuel URL with /<owner>/(models|worlds)/<name>, got: {x!r}"
            )
        owner, kind, name = parts[0], parts[1], parts[2]
        for segment in (owner, name):
            if not segment or segment in (".", "..") or "/" in segment or "\\" in segment:
                raise ValueError(f"Unsafe Fuel owner/name in URL: {x!r}")
        asset_kind: Literal["models", "worlds"] = (
            "models" if kind == "models" else "worlds"
        )
        return FuelAssetRef(
            server=parsed.netloc.lower(), owner=owner, asset_kind=asset_kind, name=name
        )
