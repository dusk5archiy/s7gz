from __future__ import annotations

from dataclasses import dataclass, field

from ..base_station import resolve_base_station_anchor
from ..formations.mechanism import LineAbreastFormation, RingFormation
from ..formations.protocol import FormationProtocol
from ..models import FleetMember, GeoPose
from ..settings import (
    AbsoluteCenterConfig,
    BaseStationCenterConfig,
    LineAbreastFormationConfig,
    RingFormationConfig,
    Settings as FleetSettings,
    WorldFleetConfig,
)
from .protocol import FleetPlannerProtocol
from .standard import StandardFleetPlanner


@dataclass(kw_only=True, frozen=True)
class ProductionFleetPlanner(FleetPlannerProtocol):
    world_key: str | None = None
    fleet_config: WorldFleetConfig | None = None
    s_fleet: FleetSettings = field(default_factory=FleetSettings.build)
    base_station_pose: GeoPose | None = None

    def resolve_config(self) -> WorldFleetConfig:
        if self.fleet_config is not None:
            return self.fleet_config
        return self.s_fleet.for_world(self.world_key)

    def _build_formation(self, cfg: WorldFleetConfig) -> FormationProtocol:
        fcfg = cfg.formation
        if isinstance(fcfg, LineAbreastFormationConfig):
            return LineAbreastFormation(
                spacing_m=fcfg.spacing_m,
                min_separation_m=fcfg.min_separation_m,
            )
        if isinstance(fcfg, RingFormationConfig):
            return RingFormation(
                radius_m=fcfg.radius_m,
                min_separation_m=fcfg.min_separation_m,
            )
        raise TypeError(f"Unsupported formation config: {fcfg!r}")

    def resolve_center(self) -> GeoPose:
        cfg = self.resolve_config()
        ccfg = cfg.center
        if isinstance(ccfg, BaseStationCenterConfig):
            formation_cfg = cfg.formation
            depth_m = (
                formation_cfg.radius_m
                if isinstance(formation_cfg, RingFormationConfig)
                else 0.0
            )
            return resolve_base_station_anchor(
                self.base_station_pose,
                base_station_half_m=ccfg.base_station_half_m,
                gap_m=ccfg.gap_m,
                depth_m=depth_m,
                front_east=ccfg.front_east,
                front_north=ccfg.front_north,
                offset_up_m=ccfg.offset_up_m,
            )
        if isinstance(ccfg, AbsoluteCenterConfig):
            return ccfg.pose
        raise TypeError(f"Unsupported center config: {ccfg!r}")

    def __call__(self) -> tuple[FleetMember, ...]:
        cfg = self.resolve_config()
        if not cfg.enabled or not cfg.vehicles:
            return ()
        return StandardFleetPlanner(
            vehicle_specs_emitter=lambda: cfg.vehicles,
            formation=self._build_formation(cfg),
            center=self.resolve_center(),
            pose_overrides=dict(cfg.pose_overrides),
        )()
