from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from ...models import AttachmentSpec, BodyPose, VehicleSpec
from ..protocol import AttachmentApplierProtocol

DEFAULT_FLASHLIGHT_POSE = BodyPose(forward_m=0.14, up_m=-0.02, pitch_rad=0.25)


@dataclass(kw_only=True, frozen=True)
class FlashlightApplier(AttachmentApplierProtocol):
    intensity: float = 5.0
    range_m: float = 30.0
    inner_angle: float = 0.6
    outer_angle: float = 1.2
    mass_kg: float = 0.010

    def __call__(
        self, *, model: ET.Element, vehicle: VehicleSpec, attachment: AttachmentSpec
    ) -> None:
        params = dict(attachment.params)
        intensity = float(params.get("intensity", self.intensity))
        range_m = float(params.get("range_m", self.range_m))
        pose = (
            attachment.pose_offset
            if attachment.pose_offset is not None
            else DEFAULT_FLASHLIGHT_POSE
        )

        parent_link = "base_link"
        if model.find("link[@name='base_link']") is None and model.find("include") is None:
            first_link = model.find("link")
            if first_link is not None and first_link.attrib.get("name"):
                parent_link = first_link.attrib["name"]

        link_name = f"{attachment.slot}_link"
        joint_name = f"{attachment.slot}_joint"

        link = ET.SubElement(model, "link", name=link_name)
        ET.SubElement(
            link, "pose", relative_to=parent_link
        ).text = pose.to_sdf_pose_str()
        inertial = ET.SubElement(link, "inertial")
        ET.SubElement(inertial, "mass").text = str(self.mass_kg)
        inertia = ET.SubElement(inertial, "inertia")
        for tag, val in (
            ("ixx", "1e-6"),
            ("iyy", "1e-6"),
            ("izz", "1e-6"),
            ("ixy", "0"),
            ("ixz", "0"),
            ("iyz", "0"),
        ):
            ET.SubElement(inertia, tag).text = val

        light = ET.SubElement(link, "light", name=attachment.slot, type="spot")
        ET.SubElement(light, "pose").text = "0 0 0 0 0 0"
        ET.SubElement(light, "diffuse").text = "1 1 1 1"
        ET.SubElement(light, "specular").text = "1 1 1 1"
        ET.SubElement(light, "intensity").text = str(intensity)
        attenuation = ET.SubElement(light, "attenuation")
        ET.SubElement(attenuation, "range").text = str(range_m)
        ET.SubElement(attenuation, "constant").text = "0.1"
        ET.SubElement(attenuation, "linear").text = "0.02"
        ET.SubElement(attenuation, "quadratic").text = "0.002"
        ET.SubElement(light, "direction").text = "1 0 0"
        spot = ET.SubElement(light, "spot")
        ET.SubElement(spot, "inner_angle").text = str(self.inner_angle)
        ET.SubElement(spot, "outer_angle").text = str(self.outer_angle)
        ET.SubElement(spot, "falloff").text = "1.0"
        ET.SubElement(light, "cast_shadows").text = "true"

        joint = ET.SubElement(model, "joint", name=joint_name, type="fixed")
        ET.SubElement(joint, "parent").text = parent_link
        ET.SubElement(joint, "child").text = link_name


__all__ = ["FlashlightApplier"]
