from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src_sim.settings.asset_ref import resolve_world_generated_models_dir
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
    world_key: str | None = None
    models_dir: Path | None = None
    gz_model_name_transform: GzModelNameTransformProtocol = field(
        default_factory=ProductionGzModelNameTransform
    )

    def resolve_models_dir(self) -> Path:
        if self.models_dir is not None:
            return self.models_dir
        return resolve_world_generated_models_dir(
            self.world_key, resource=self.s_resource
        )

    def __call__(self, *, vehicle: VehicleSpec) -> Path:
        target_dir = self.resolve_models_dir()
        return ScaffoldVehicleModelBuilder(
            airframe_builder=GenericSdfAirframeBuilder(
                s_resource=self.s_resource,
                models_dir=target_dir,
                gz_model_name_transform=self.gz_model_name_transform,
            ),
            attachment_applier=AttachmentApplierRegistry(
                appliers={"flashlight": FlashlightApplier()}
            ),
            device_applier=DeviceApplierRegistry(
                appliers={"scan_lidar": ScanLidarApplier()}
            ),
            package_writer=StandardSdfModelPackageWriter(
                models_dir=target_dir,
                s_resource=self.s_resource,
                gz_model_name_transform=self.gz_model_name_transform,
            ),
        )(vehicle=vehicle)
