from __future__ import annotations

from dataclasses import dataclass

from ..models import DeviceSpec, VehicleSpec
from .protocol import DeviceApplierProtocol


@dataclass(kw_only=True, frozen=True)
class DeviceApplierRegistry(DeviceApplierProtocol):
    appliers: dict[str, DeviceApplierProtocol]

    def __call__(self, *, model, vehicle: VehicleSpec, device: DeviceSpec) -> None:
        applier = self.appliers.get(device.kind)
        if applier is None:
            raise KeyError(
                f"Unknown device kind {device.kind!r}; available: {sorted(self.appliers)}"
            )
        applier(model=model, vehicle=vehicle, device=device)
