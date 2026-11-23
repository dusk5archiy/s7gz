from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from src_sim.fuel.fs import atomic_path

from .airframes.px4_generic import resolve_airframe_sdf_path
from .gz_model_name_transforms.production import ProductionGzModelNameTransform
from .gz_model_name_transforms.protocol import GzModelNameTransformProtocol
from .models import VehicleSpec
from .protocol import ModelPackageWriterProtocol


def render_sdf(root: ET.Element) -> str:
    ET.indent(root, space="  ")
    return '<?xml version="1.0" ?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def build_model_config_xml(*, model_name: str, sdf_version: str, description: str) -> str:
    root = ET.Element("model")
    ET.SubElement(root, "name").text = model_name
    ET.SubElement(root, "version").text = "1.0"
    ET.SubElement(root, "sdf", version=sdf_version).text = "model.sdf"
    if description:
        ET.SubElement(root, "description").text = description
    return render_sdf(root)


def _copy_sibling_assets(*, src_dir: Path, dst_dir: Path) -> None:
    """Copy local asset folders/files (meshes/, materials/, etc.) next to the source SDF."""
    if not src_dir.is_dir() or src_dir.resolve() == dst_dir.resolve():
        return
    dst_dir.mkdir(parents=True, exist_ok=True)
    for entry in src_dir.iterdir():
        if entry.name in {"model.sdf", "model.config"} or entry.name.startswith("."):
            continue
        target = dst_dir / entry.name
        if entry.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(entry, target)
        elif entry.is_file():
            shutil.copy2(entry, target)


@dataclass(kw_only=True, frozen=True)
class StandardSdfModelPackageWriter(ModelPackageWriterProtocol):
    models_dir: Path
    gz_model_name_transform: GzModelNameTransformProtocol = field(
        default_factory=ProductionGzModelNameTransform
    )

    def __call__(self, *, vehicle: VehicleSpec, sdf_root: ET.Element) -> Path:
        gz_model_name = self.gz_model_name_transform(vehicle.namespace)
        model_dir = self.models_dir / gz_model_name
        if vehicle.airframe is not None:
            try:
                src_sdf = resolve_airframe_sdf_path(vehicle.airframe)
                _copy_sibling_assets(src_dir=src_sdf.parent, dst_dir=model_dir)
            except (FileNotFoundError, ValueError):
                pass

        with atomic_path(model_dir / "model.sdf") as tmp_path:
            tmp_path.write_text(render_sdf(sdf_root), encoding="utf-8")
        with atomic_path(model_dir / "model.config") as tmp_path:
            tmp_path.write_text(
                build_model_config_xml(
                    model_name=gz_model_name,
                    sdf_version=sdf_root.get("version") or "1.9",
                    description=f"Generated vehicle model ({vehicle.airframe}) for {vehicle.namespace}",
                ),
                encoding="utf-8",
            )
        return model_dir
