from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .resource import ResourceSettings


@dataclass(kw_only=True, frozen=True)
class CatalogAssetRef:
    """Reference to an asset managed under source_worlds/ or source_models/ (auto-prefers patched_*)."""

    kind: Literal["catalog"] = "catalog"
    """Discriminator for catalog-managed assets."""
    relative_path: str
    """Relative path under source_worlds/ or source_models/ (e.g. 'px4/forest.sdf', 'px4/x500/model.sdf')."""


@dataclass(kw_only=True, frozen=True)
class PathAssetRef:
    """Direct filesystem path to an SDF asset (relative to cwd or absolute inside the sim container)."""

    kind: Literal["path"] = "path"
    """Discriminator for direct path assets."""
    path: Path
    """Relative (from project root / cwd) or absolute path (e.g. '/opt/ros/.../empty.sdf')."""


AssetRef = CatalogAssetRef | PathAssetRef


def _validate_catalog_rel_path(relative_path: str) -> str:
    cleaned = relative_path.strip().lstrip("/")
    if not cleaned or "\\" in cleaned or ".." in cleaned.split("/"):
        raise ValueError(f"Invalid catalog relative_path: {relative_path!r}")
    return cleaned


def asset_ref_to_key(ref: AssetRef | None) -> str | None:
    """Convert an AssetRef into a canonical string key suitable for JSON dict keys and URL params."""
    if ref is None:
        return None
    if isinstance(ref, CatalogAssetRef):
        cleaned = ref.relative_path.strip().lstrip("/")
        return f"catalog:{cleaned}" if cleaned else None
    raw = ref.path.expanduser().as_posix().strip()
    return f"path:{raw}" if raw else None


def asset_ref_from_key(key: str | None) -> AssetRef | None:
    """Parse a canonical string key ('catalog:...' or 'path:...') back into an AssetRef."""
    if not key:
        return None
    cleaned = key.strip()
    if not cleaned:
        return None
    if cleaned.startswith("catalog:"):
        rel = cleaned.removeprefix("catalog:").strip().lstrip("/")
        return CatalogAssetRef(relative_path=rel) if rel else None
    if cleaned.startswith("path:"):
        raw = cleaned.removeprefix("path:").strip()
        return PathAssetRef(path=Path(raw)) if raw else None
    return PathAssetRef(path=Path(cleaned))


def world_ref_from_path(
    world_path: Path | str,
    *,
    resource: ResourceSettings | None = None,
) -> AssetRef:
    """Map an on-disk world path into CatalogAssetRef if under source_worlds/patched_worlds, else PathAssetRef."""
    res = resource or ResourceSettings.build()
    cwd = Path.cwd().resolve()
    p = Path(str(world_path).strip()).expanduser()
    resolved = p.resolve() if p.is_absolute() else (cwd / p).resolve()

    for root in (res.source_worlds_dir.resolve(), res.patched_worlds_dir.resolve()):
        if resolved.is_relative_to(root):
            return CatalogAssetRef(relative_path=resolved.relative_to(root).as_posix())

    if resolved.is_relative_to(cwd):
        return PathAssetRef(path=Path(resolved.relative_to(cwd).as_posix()))
    return PathAssetRef(path=p)


def resolve_world_asset_path(
    ref: AssetRef,
    *,
    resource: ResourceSettings | None = None,
    prefer_patched: bool = False,
) -> Path:
    """Resolve a World AssetRef to a filesystem Path."""
    res = resource or ResourceSettings.build()
    if isinstance(ref, CatalogAssetRef):
        rel = _validate_catalog_rel_path(ref.relative_path)
        if prefer_patched:
            patched = res.patched_worlds_dir / rel
            if patched.is_file():
                return patched
        return res.source_worlds_dir / rel
    return ref.path.expanduser()


def resolve_model_asset_path(
    ref: AssetRef,
    *,
    resource: ResourceSettings | None = None,
    prefer_patched: bool = True,
) -> Path:
    """Resolve a Model/Airframe AssetRef to its SDF Path (Catalog refs auto-prefer patched_models/)."""
    res = resource or ResourceSettings.build()
    if isinstance(ref, CatalogAssetRef):
        rel = _validate_catalog_rel_path(ref.relative_path)
        candidates: list[Path] = []
        if prefer_patched:
            candidates.append(res.patched_models_dir / rel)
        candidates.append(res.source_models_dir / rel)
        for cand in candidates:
            if cand.is_dir():
                sdf = cand / "model.sdf"
                if sdf.is_file():
                    return sdf
            elif cand.is_file():
                return cand
        return candidates[-1]

    p = ref.path.expanduser()
    if p.is_dir():
        return p / "model.sdf"
    return p


__all__ = [
    "AssetRef",
    "CatalogAssetRef",
    "PathAssetRef",
    "asset_ref_from_key",
    "asset_ref_to_key",
    "resolve_model_asset_path",
    "resolve_world_asset_path",
    "world_ref_from_path",
]
