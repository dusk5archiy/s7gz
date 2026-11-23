from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal

from s7dcls import Gt, StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX
from src_sim.settings.asset_ref import (
    AssetRef,
    CatalogAssetRef,
    PathAssetRef,
    asset_ref_from_key,
    asset_ref_to_key,
    world_ref_from_path,
)
from src_sim.settings.resource import ResourceSettings
from src_sim.stage_vehicle.models import VehicleSpec

from .models import GeoPose

PREFIX = SIM_ENV_PREFIX + "FLEET__"


@dataclass(kw_only=True, frozen=True)
class LineAbreastFormationConfig:
    """Arrange vehicles side-by-side along a straight horizontal line."""

    kind: Literal["line_abreast"] = "line_abreast"
    """Formation discriminator."""
    spacing_m: Annotated[float, Gt(limit=0.0)] = 2.5
    """Lateral distance between adjacent vehicles in meters."""
    min_separation_m: Annotated[float, Gt(limit=0.0)] = 1.0
    """Minimum allowed separation distance between vehicles in meters."""


@dataclass(kw_only=True, frozen=True)
class RingFormationConfig:
    """Arrange vehicles evenly around a circle of fixed radius."""

    kind: Literal["ring"] = "ring"
    """Formation discriminator."""
    radius_m: Annotated[float, Gt(limit=0.0)] = 3.0
    """Circle radius from the formation center in meters."""
    min_separation_m: Annotated[float, Gt(limit=0.0)] = 1.0
    """Minimum allowed chord separation between adjacent vehicles in meters."""


FormationConfig = LineAbreastFormationConfig | RingFormationConfig


@dataclass(kw_only=True, frozen=True)
class BaseStationCenterConfig:
    """Place the fleet center in front of the world's base_station with standoff (or origin if absent)."""

    kind: Literal["base_station"] = "base_station"
    """Center anchor mode discriminator."""
    base_station_half_m: float = 1.5
    """Half-width of the base_station tent footprint in meters."""
    gap_m: float = 3.0
    """Clearance gap in front of the base_station tent in meters."""
    front_east: float = 0.0
    """Local +X (East) component of the base_station front direction."""
    front_north: float = 1.0
    """Local +Y (North) component of the base_station front direction."""
    offset_up_m: float = 0.3
    """Vertical offset in meters above base_station (or ground origin)."""


@dataclass(kw_only=True, frozen=True)
class AbsoluteCenterConfig:
    """Place the fleet center at an explicit absolute world ENU pose."""

    kind: Literal["absolute"] = "absolute"
    """Center anchor mode discriminator."""
    pose: GeoPose = field(default_factory=lambda: GeoPose(up_m=0.3))
    """Explicit world ENU pose (meters and degrees)."""


CenterConfig = BaseStationCenterConfig | AbsoluteCenterConfig


@dataclass(kw_only=True, frozen=True)
class WorldFleetConfig:
    """Complete fleet configuration bound to a specific world SDF path."""

    enabled: bool = True
    """Enable fleet generation and spawning into this world SDF."""
    formation: FormationConfig = field(default_factory=LineAbreastFormationConfig)
    """Selected formation layout and its formation-specific parameters."""
    center: CenterConfig = field(default_factory=BaseStationCenterConfig)
    """Fleet center anchor mode (relative to base_station or explicit absolute pose)."""
    pose_overrides: dict[str, GeoPose] = field(default_factory=dict)
    """Optional per-vehicle namespace pose overrides in world ENU coordinates."""
    vehicles: tuple[VehicleSpec, ...] = ()
    """Ordered list of vehicles to spawn in this world (empty by default)."""


def resolve_world_fleet_key(
    world: AssetRef | Path | str | None,
    *,
    resource: ResourceSettings | None = None,
) -> str | None:
    """Normalize any World AssetRef or path to its canonical fleet dict key.

    Examples:
        - CatalogAssetRef(relative_path='px4/forest.sdf') -> 'catalog:px4/forest.sdf'
        - Path('runtime/source_worlds/px4/forest.sdf')    -> 'catalog:px4/forest.sdf'
        - PathAssetRef(path=Path('/opt/ros/.../empty.sdf')) -> 'path:/opt/ros/.../empty.sdf'
    """
    if world is None:
        return None
    if isinstance(world, (CatalogAssetRef, PathAssetRef)):
        return asset_ref_to_key(world)
    raw = str(world).strip()
    if not raw:
        return None
    if raw.startswith("catalog:") or raw.startswith("path:"):
        parsed = asset_ref_from_key(raw)
        return asset_ref_to_key(parsed)
    ref = world_ref_from_path(raw, resource=resource)
    return asset_ref_to_key(ref)


@dataclass(kw_only=True, frozen=True)
class Settings:
    """Per-world fleet configurations keyed by world SDF path (e.g. `runtime/source_worlds/px4/forest.sdf`)."""

    worlds: dict[str, WorldFleetConfig] = field(default_factory=dict)
    """Map of world SDF path -> fleet config. Worlds absent from this map default to an empty fleet."""

    def for_world(self, world_key: str | None) -> WorldFleetConfig:
        if not world_key:
            return WorldFleetConfig()
        if world_key in self.worlds:
            return self.worlds[world_key]
        normalized = resolve_world_fleet_key(world_key)
        if normalized and normalized in self.worlds:
            return self.worlds[normalized]
        return WorldFleetConfig()

    @classmethod
    def build(cls) -> Settings:
        return StandardDataclassFetcher.Args(
            datacls=Settings,
            dict_emitter=StandardShellDictFetcher(prefix=PREFIX),
        ).build()()
