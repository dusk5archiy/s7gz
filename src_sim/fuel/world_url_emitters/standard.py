from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from s7dcls import EmitterProtocol, FunctionProtocol


@dataclass(kw_only=True, frozen=True)
class JsonCatalogLoader(EmitterProtocol[dict[str, str]]):
    catalog_file: Path

    def __call__(self) -> dict[str, str]:
        raw = json.loads(self.catalog_file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise TypeError(f"Expected JSON object in {self.catalog_file}")
        catalog: dict[str, str] = {}
        for key, value in raw.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Invalid URL entry for {key!r} in {self.catalog_file}"
                )
            catalog[str(key)] = value.strip()
        return catalog


@dataclass(kw_only=True, frozen=True)
class StandardFuelWorldUrlBuilder(FunctionProtocol[str, str]):
    canonical_server: str
    default_owner: str = "OpenRobotics"
    scheme: str = "https"

    def __call__(self, x: str) -> str:
        raw = x.strip()
        if "/" in raw:
            parts = [p.strip() for p in raw.split("/")]
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError(
                    f"Expected '<owner>/<world_name>' or '<world_name>', got: {x!r}"
                )
            owner, name = parts[0], parts[1]
        else:
            owner, name = self.default_owner, raw
        return (
            f"{self.scheme}://{self.canonical_server}/1.0/"
            f"{quote(owner, safe='')}/worlds/{quote(name, safe='')}"
        )
