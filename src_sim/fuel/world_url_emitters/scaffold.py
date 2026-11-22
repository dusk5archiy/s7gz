from __future__ import annotations

from dataclasses import dataclass

from s7dcls import EmitterProtocol, FunctionProtocol


@dataclass(kw_only=True, frozen=True)
class ScaffoldWorldUrlEmitter(EmitterProtocol[str | None]):
    world_name: str | None
    world_url: str | None
    catalog_loader: EmitterProtocol[dict[str, str]]
    fallback_url_builder: FunctionProtocol[str, str]

    def __call__(self) -> str | None:
        if self.world_url is not None and self.world_url.strip():
            return self.world_url.strip()
        if self.world_name is None or not self.world_name.strip():
            return None

        key = self.world_name.strip()
        catalog = self.catalog_loader()
        if key in catalog:
            return catalog[key]

        return self.fallback_url_builder(key)
