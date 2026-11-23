from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from s7dcls import EmitterProtocol

from src_sim.settings.asset_ref import AssetRef, PathAssetRef
from src_sim.stage_vehicle.models import AttachmentSpec, DeviceSpec, VehicleSpec


@dataclass(kw_only=True, frozen=True)
class HomogeneousVehicleSpecsEmitter(EmitterProtocol[tuple[VehicleSpec, ...]]):
    count: int
    airframe: AssetRef | Path
    namespace_prefix: str
    index_separator: str
    attachments: tuple[AttachmentSpec, ...] = ()
    devices: tuple[DeviceSpec, ...] = ()

    def __call__(self) -> tuple[VehicleSpec, ...]:
        resolved_airframe: AssetRef = (
            PathAssetRef(path=self.airframe)
            if isinstance(self.airframe, Path)
            else self.airframe
        )
        specs: list[VehicleSpec] = []
        for idx in range(self.count):
            ns = f"{self.namespace_prefix}{self.index_separator}{idx}"
            specs.append(
                VehicleSpec(
                    namespace=ns,
                    airframe=resolved_airframe,
                    attachments=self.attachments,
                    devices=self.devices,
                )
            )
        return tuple(specs)
