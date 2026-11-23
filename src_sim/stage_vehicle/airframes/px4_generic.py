from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from src_sim.fuel.ignition_plugin_transforms import IgnitionPluginTransform
from src_sim.fuel.uri_localizers.production import ProductionFuelUriLocalizer
from src_sim.model_uris import (
    canonicalize_sdf_element_uris,
    ensure_model_wrappers,
    infer_provider_from_path,
    parse_sdf_xml_with_ns_fix,
)
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


def _resolve_source_model_dir_for_sdf(
    sdf_path: Path, *, resource: ResourceSettings
) -> Path:
    """Return the corresponding `source_models/` dir if `sdf_path` is a patched wrapper, else `sdf_path.parent`."""
    parent = sdf_path.parent.resolve()
    patched_root = resource.patched_models_dir.resolve()
    source_root = resource.source_models_dir.resolve()
    if parent.is_relative_to(patched_root):
        rel = parent.relative_to(patched_root)
        cand = (source_root / rel).resolve()
        if cand.is_relative_to(source_root) and cand.is_dir():
            return cand
    return parent


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

    s_resource: ResourceSettings = field(default_factory=ResourceSettings.build)
    models_dir: Path | None = None
    gz_model_name_transform: GzModelNameTransformProtocol = field(
        default_factory=ProductionGzModelNameTransform
    )
    pose_publisher_update_frequency: int = 30

    def __call__(self, *, vehicle: VehicleSpec) -> ET.Element:
        sdf_path = resolve_airframe_sdf_path(vehicle.airframe, resource=self.s_resource)
        gz_model_name = self.gz_model_name_transform(vehicle.namespace)
        raw_text = sdf_path.read_text(encoding="utf-8", errors="replace")
        if "https://fuel." in raw_text or "http://fuel." in raw_text:
            raw_text = ProductionFuelUriLocalizer(s_resource=self.s_resource)(raw_text)
        raw_text = IgnitionPluginTransform()(raw_text)
        root = parse_sdf_xml_with_ns_fix(raw_text)
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

        provider = infer_provider_from_path(sdf_path, resource=self.s_resource)
        src_model_dir = _resolve_source_model_dir_for_sdf(
            sdf_path, resource=self.s_resource
        )
        ext_prefix: str | None = None
        if self.models_dir is not None:
            runtime_root = self.s_resource.runtime_dir.resolve()
            gen_model_dir = (self.models_dir / gz_model_name).resolve()
            if gen_model_dir.is_relative_to(runtime_root):
                ext_prefix = gen_model_dir.relative_to(runtime_root).as_posix()

        deps = canonicalize_sdf_element_uris(
            model,
            resource=self.s_resource,
            provider=provider,
            src_model_dir=src_model_dir,
            external_model_uri_prefix=ext_prefix or gz_model_name,
        )
        if deps:
            ensure_model_wrappers(deps, resource=self.s_resource)

        _inject_motor_namespace(model, robot_namespace=gz_model_name)
        _ensure_pose_publisher(
            model,
            update_frequency=self.pose_publisher_update_frequency,
        )
        return root


GenericPx4AirframeBuilder = GenericSdfAirframeBuilder
