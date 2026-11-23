from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .airframes.protocol import AirframeBuilderProtocol
from .attachments.protocol import AttachmentApplierProtocol
from .devices.protocol import DeviceApplierProtocol
from .models import VehicleSpec
from .protocol import ModelPackageWriterProtocol, VehicleModelBuilderProtocol


@dataclass(kw_only=True, frozen=True)
class ScaffoldVehicleModelBuilder(VehicleModelBuilderProtocol):
    airframe_builder: AirframeBuilderProtocol
    attachment_applier: AttachmentApplierProtocol
    device_applier: DeviceApplierProtocol
    package_writer: ModelPackageWriterProtocol

    def __call__(self, *, vehicle: VehicleSpec) -> Path:
        sdf_root = self.airframe_builder(vehicle=vehicle)
        model = sdf_root.find("model")
        if model is None:
            raise ValueError(
                f"Airframe builder returned SDF without <model> for {vehicle.namespace!r}"
            )
        for attachment in vehicle.attachments:
            self.attachment_applier(model=model, vehicle=vehicle, attachment=attachment)
        for device in vehicle.devices:
            self.device_applier(model=model, vehicle=vehicle, device=device)
        return self.package_writer(vehicle=vehicle, sdf_root=sdf_root)
