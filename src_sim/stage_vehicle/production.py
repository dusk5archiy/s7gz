from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src_sim.settings.resource import ResourceSettings

from .airframes.px4_generic import GenericSdfAirframeBuilder
from .attachments.mechanism import FlashlightApplier
from .attachments.scaffold import AttachmentApplierRegistry
from .devices.mechanism import ScanLidarApplier
from .devices.scaffold import DeviceApplierRegistry
from .gz_model_name_transforms.production import ProductionGzModelNameTransform
from .gz_model_name_transforms.protocol import GzModelNameTransformProtocol
from .models import VehicleSpec
from .protocol import VehicleModelBuilderProtocol
from .scaffold import ScaffoldVehicleModelBuilder
from .standard import StandardSdfModelPackageWriter


@dataclass(kw_only=True, frozen=True)
class ProductionVehicleModelBuilder(VehicleModelBuilderProtocol):
    s_resource: ResourceSettings = field(default_factory=ResourceSettings.build)
    gz_model_name_transform: GzModelNameTransformProtocol = field(
        default_factory=ProductionGzModelNameTransform
    )

    def __call__(self, *, vehicle: VehicleSpec) -> Path:
        models_dir = self.s_resource.generated_models_dir
        return ScaffoldVehicleModelBuilder(
            airframe_builder=GenericSdfAirframeBuilder(
                gz_model_name_transform=self.gz_model_name_transform
            ),
            attachment_applier=AttachmentApplierRegistry(
                appliers={"flashlight": FlashlightApplier()}
            ),
            device_applier=DeviceApplierRegistry(
                appliers={"scan_lidar": ScanLidarApplier()}
            ),
            package_writer=StandardSdfModelPackageWriter(
                models_dir=models_dir,
                gz_model_name_transform=self.gz_model_name_transform,
            ),
        )(vehicle=vehicle)
