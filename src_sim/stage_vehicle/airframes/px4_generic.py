from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from src_sim.settings.asset_ref import (
    AssetRef,
    PathAssetRef,
    resolve_model_asset_path,
)
from src_sim.settings.resource import ResourceSettings

from ..gz_model_name_transforms.production import ProductionGzModelNameTransform
from ..gz_model_name_transforms.protocol import GzModelNameTransformProtocol
from ..models import VehicleSpec
from .protocol import AirframeBuilderProtocol

_SDF_TAG_RE = re.compile(r"<sdf\b([^>]*)>", re.IGNORECASE)
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_LOCAL_ASSET_TAGS = {
    "uri",
    "albedo_map",
    "normal_map",
    "roughness_map",
    "metalness_map",
    "emissive_map",
    "diffuse",
    "normal",
}


def resolve_airframe_sdf_path(
    airframe: AssetRef | Path | None,
    *,
    resource: ResourceSettings | None = None,
) -> Path:
    if airframe is None:
        raise ValueError("Vehicle airframe is required")
    ref: AssetRef = PathAssetRef(path=airframe) if isinstance(airframe, Path) else airframe
    target = resolve_model_asset_path(ref, resource=resource, prefer_patched=True)
    resolved = target.expanduser().resolve()
    if resolved.is_dir():
        candidate = resolved / "model.sdf"
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"model.sdf not found in airframe directory: {resolved}")
    if not resolved.is_file():
        raise FileNotFoundError(f"Airframe SDF not found: {resolved}")
    return resolved


def _parse_sdf_with_ns_fix(sdf_path: Path) -> ET.Element:
    xml_text = sdf_path.read_text(encoding="utf-8", errors="replace").lstrip()
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError:
        def _add_ns(match: re.Match[str]) -> str:
            attrs = match.group(1)
            extra = ""
            if "xmlns:gz=" not in attrs:
                extra += ' xmlns:gz="http://gazebosim.org/schema"'
            if "xmlns:ignition=" not in attrs:
                extra += ' xmlns:ignition="http://ignitionrobotics.org/schema"'
            return f"<sdf{attrs}{extra}>"

        return ET.fromstring(_SDF_TAG_RE.sub(_add_ns, xml_text, count=1))


def _rewrite_relative_asset_uris(
    model: ET.Element, *, model_dir: Path, gz_model_name: str
) -> None:
    """Rewrite relative local URIs (e.g. `meshes/body.dae`) to `model://<gz_model_name>/...`."""
    resolved_dir = model_dir.resolve()
    for el in model.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag not in _LOCAL_ASSET_TAGS or not el.text:
            continue
        raw = el.text.strip()
        if not raw or _SCHEME_RE.match(raw) or raw.startswith("/"):
            continue
        candidate = (resolved_dir / raw).resolve()
        if candidate.is_relative_to(resolved_dir) and candidate.exists():
            rel = candidate.relative_to(resolved_dir).as_posix()
            el.text = f"model://{gz_model_name}/{rel}"


def _ensure_pose_publisher(model: ET.Element, *, update_frequency: int = 30) -> None:
    for plugin in model.findall("plugin"):
        if "PosePublisher" in (plugin.attrib.get("filename") or "") or "PosePublisher" in (
            plugin.attrib.get("name") or ""
        ):
            return
    plugin = ET.SubElement(
        model,
        "plugin",
        filename="gz-sim-pose-publisher-system",
        name="gz::sim::systems::PosePublisher",
    )
    for tag, val in (
        ("publish_model_pose", "true"),
        ("publish_link_pose", "true"),
        ("publish_collision_pose", "false"),
        ("publish_visual_pose", "false"),
        ("publish_nested_model_pose", "false"),
        ("update_frequency", str(update_frequency)),
    ):
        ET.SubElement(plugin, tag).text = val


def _inject_motor_namespace(model: ET.Element, *, robot_namespace: str) -> None:
    for plugin in model.findall("plugin"):
        filename = plugin.attrib.get("filename") or ""
        name = plugin.attrib.get("name") or ""
        if "multicopter-motor-model" in filename or "MulticopterMotorModel" in name:
            ns_el = plugin.find("robotNamespace")
            if ns_el is None:
                ns_el = ET.SubElement(plugin, "robotNamespace")
            ns_el.text = robot_namespace


@dataclass(kw_only=True, frozen=True)
class GenericSdfAirframeBuilder(AirframeBuilderProtocol):
    """Build a vehicle SDF uniformly from any model SDF path (PX4, Fuel, or custom)."""

    gz_model_name_transform: GzModelNameTransformProtocol = field(
        default_factory=ProductionGzModelNameTransform
    )
    pose_publisher_update_frequency: int = 30

    def __call__(self, *, vehicle: VehicleSpec) -> ET.Element:
        sdf_path = resolve_airframe_sdf_path(vehicle.airframe)
        gz_model_name = self.gz_model_name_transform(vehicle.namespace)
        root = _parse_sdf_with_ns_fix(sdf_path)
        if root.tag == "model":
            wrapper = ET.Element("sdf", version="1.9")
            wrapper.append(root)
            root = wrapper
        model = root.find("model")
        if model is None:
            # Handle SDF files with top-level <include> elements (e.g. atmos, spacecraft_2d).
            includes = list(root.findall("include"))
            if not includes:
                raise ValueError(f"No <model> or <include> element in {sdf_path}")
            model = ET.SubElement(root, "model", name=gz_model_name)
            for inc in includes:
                root.remove(inc)
                model.append(inc)
        model.attrib["name"] = gz_model_name
        _rewrite_relative_asset_uris(
            model,
            model_dir=sdf_path.parent,
            gz_model_name=gz_model_name,
        )
        _inject_motor_namespace(model, robot_namespace=gz_model_name)
        _ensure_pose_publisher(
            model,
            update_frequency=self.pose_publisher_update_frequency,
        )
        return root


GenericPx4AirframeBuilder = GenericSdfAirframeBuilder
