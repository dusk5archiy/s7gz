from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ModelLayout = Literal["fuel_tree", "flat"]


@dataclass(frozen=True)
class AssetProviderSpec:
    """Descriptor for an external asset provider (e.g. Fuel, PX4, custom)."""

    key: str
    label: str
    model_layout: ModelLayout
    supports_download: bool = False
    supports_sync: bool = False
    can_delete_source: bool = False


PROVIDERS: dict[str, AssetProviderSpec] = {
    "fuel": AssetProviderSpec(
        key="fuel",
        label="Fuel",
        model_layout="fuel_tree",
        supports_download=True,
        supports_sync=False,
        can_delete_source=True,
    ),
    "px4": AssetProviderSpec(
        key="px4",
        label="PX4",
        model_layout="flat",
        supports_download=False,
        supports_sync=True,
        can_delete_source=False,
    ),
}


def get_provider(key: str) -> AssetProviderSpec:
    cleaned = key.strip().lower()
    if cleaned not in PROVIDERS:
        raise ValueError(f"Unknown asset provider: {key!r}")
    return PROVIDERS[cleaned]


def provider_from_rel_path(relative_path: str) -> tuple[AssetProviderSpec, str]:
    cleaned = relative_path.strip().lstrip("/")
    if "/" not in cleaned:
        raise ValueError(f"Expected '<provider>/<path>', got: {relative_path!r}")
    prov_key, rest = cleaned.split("/", 1)
    if not rest.strip():
        raise ValueError(f"Missing path under provider {prov_key!r}")
    return get_provider(prov_key), rest


__all__ = [
    "AssetProviderSpec",
    "ModelLayout",
    "PROVIDERS",
    "get_provider",
    "provider_from_rel_path",
]
