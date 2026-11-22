from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal


@dataclass(kw_only=True, frozen=True, order=True)
class FuelAssetId:
    """Canonical case-insensitive identity `(owner, asset_kind, name)` across Fuel mirrors."""

    owner: str
    asset_kind: Literal["models", "worlds"]
    name: str


@dataclass(kw_only=True, frozen=True)
class FuelAssetRef:
    """Normalized identity of a Fuel model or world asset including source server."""

    server: str
    owner: str
    asset_kind: Literal["models", "worlds"]
    name: str

    @property
    def id(self) -> FuelAssetId:
        return FuelAssetId(
            owner=self.owner.lower(),
            asset_kind=self.asset_kind,
            name=self.name.lower(),
        )


@dataclass(kw_only=True, frozen=True)
class FuelManifest:
    """Validated version and relative file paths for a remote Fuel asset."""

    version: str
    files: tuple[str, ...]

    def __post_init__(self) -> None:
        ver = self.version.strip()
        if not ver or ver in (".", "..") or "/" in ver or "\\" in ver:
            raise ValueError(f"Unsafe Fuel version string: {self.version!r}")
        if not self.files:
            raise ValueError("Empty Fuel asset manifest")
        for rel_path in self.files:
            if (
                not rel_path
                or "\\" in rel_path
                or rel_path.startswith("/")
                or ".." in PurePosixPath(rel_path).parts
            ):
                raise ValueError(f"Unsafe file path in manifest: {rel_path!r}")


@dataclass(kw_only=True, frozen=True)
class FuelUriMatch:
    asset: FuelAssetRef
    subpath: str | None = None
    trailing_ws: str = ""
