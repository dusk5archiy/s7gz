from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from ...gz_model_name_transforms.production import ProductionGzModelNameTransform
from ...gz_model_name_transforms.protocol import GzModelNameTransformProtocol
from ...models import BodyPose, DeviceSpec, VehicleSpec
from ..protocol import DeviceApplierProtocol

DEFAULT_SCAN_LIDAR_POSE = BodyPose(up_m=0.12)


@dataclass(kw_only=True, frozen=True)
class ScanLidarApplier(DeviceApplierProtocol):
    gz_model_name_transform: GzModelNameTransformProtocol = field(
        default_factory=ProductionGzModelNameTransform, init=False, repr=False
    )
    h_samples: int = 180
    v_samples: int = 16
    v_min_deg: float = -15.0
    v_max_deg: float = 15.0
    min_range_m: float = 0.1
    max_range_m: float = 29.0
    update_rate_hz: float = 10.0
    noise_stddev_m: float = 0.01
    mass_kg: float = 0.05

    def __call__(
        self, *, model: ET.Element, vehicle: VehicleSpec, device: DeviceSpec
    ) -> None:
        params = dict(device.params)
        h_samples = int(params.get("h_samples", self.h_samples))
        v_samples = int(params.get("v_samples", self.v_samples))
        v_min_deg = float(params.get("v_min_deg", self.v_min_deg))
        v_max_deg = float(params.get("v_max_deg", self.v_max_deg))
        min_range_m = float(params.get("min_range_m", self.min_range_m))
        max_range_m = float(params.get("max_range_m", self.max_range_m))
        update_rate_hz = float(params.get("update_rate_hz", self.update_rate_hz))
        noise_stddev_m = float(params.get("noise_stddev_m", self.noise_stddev_m))
        pose = (
            device.pose_offset
            if device.pose_offset is not None
            else DEFAULT_SCAN_LIDAR_POSE
        )
        parent_link = "base_link"
        if model.find("link[@name='base_link']") is None and model.find("include") is None:
            first_link = model.find("link")
            if first_link is not None and first_link.attrib.get("name"):
                parent_link = first_link.attrib["name"]

        link_name = f"{device.name}_link"

        link = ET.SubElement(model, "link", name=link_name)
        ET.SubElement(
            link, "pose", relative_to=parent_link
        ).text = pose.to_sdf_pose_str()
        inertial = ET.SubElement(link, "inertial")
        ET.SubElement(inertial, "mass").text = str(self.mass_kg)
        inertia = ET.SubElement(inertial, "inertia")
        for tag, val in (
            ("ixx", "1e-5"),
            ("iyy", "1e-5"),
            ("izz", "1e-5"),
            ("ixy", "0"),
            ("ixz", "0"),
            ("iyz", "0"),
        ):
            ET.SubElement(inertia, tag).text = val

        gz_model_name = (
            model.attrib.get("name") or self.gz_model_name_transform(vehicle.namespace)
        )
        sensor = ET.SubElement(link, "sensor", name=device.name, type="gpu_lidar")
        ET.SubElement(sensor, "pose").text = "0 0 0 0 0 0"
        ET.SubElement(sensor, "topic").text = f"/model/{gz_model_name}/device/{device.name}"
        ET.SubElement(sensor, "frame_id").text = link_name
        ET.SubElement(sensor, "update_rate").text = f"{update_rate_hz:g}"
        ray = ET.SubElement(sensor, "ray")
        scan = ET.SubElement(ray, "scan")
        horizontal = ET.SubElement(scan, "horizontal")
        ET.SubElement(horizontal, "samples").text = str(h_samples)
        ET.SubElement(horizontal, "resolution").text = "1"
        ET.SubElement(horizontal, "min_angle").text = f"{-math.pi:.6f}"
        ET.SubElement(horizontal, "max_angle").text = f"{math.pi:.6f}"
        vertical = ET.SubElement(scan, "vertical")
        ET.SubElement(vertical, "samples").text = str(v_samples)
        ET.SubElement(vertical, "resolution").text = "1"
        ET.SubElement(vertical, "min_angle").text = f"{math.radians(v_min_deg):.6f}"
        ET.SubElement(vertical, "max_angle").text = f"{math.radians(v_max_deg):.6f}"
        ranges = ET.SubElement(ray, "range")
        ET.SubElement(ranges, "min").text = f"{min_range_m:g}"
        ET.SubElement(ranges, "max").text = f"{max_range_m:g}"
        ET.SubElement(ranges, "resolution").text = "0.01"
        noise = ET.SubElement(ray, "noise")
        ET.SubElement(noise, "type").text = "gaussian"
        ET.SubElement(noise, "mean").text = "0"
        ET.SubElement(noise, "stddev").text = f"{noise_stddev_m:g}"
        ET.SubElement(sensor, "always_on").text = "1"
        ET.SubElement(sensor, "visualize").text = "false"

        joint = ET.SubElement(model, "joint", name=f"{device.name}_joint", type="fixed")
        ET.SubElement(joint, "parent").text = parent_link
        ET.SubElement(joint, "child").text = link_name


__all__ = ["ScanLidarApplier"]
