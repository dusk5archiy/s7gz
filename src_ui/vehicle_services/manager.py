from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src_sim.fuel.cache_resolvers.production import ProductionCacheResolver
from src_sim.fuel.uri_rules.production import ProductionFuelUriRule
from src_sim.settings.resource import ResourceSettings
from src_sim.stage_fleet.fleet_planners.production import ProductionFleetPlanner
from src_sim.stage_vehicle.production import ProductionVehicleModelBuilder
from src_ui.world_services.scene_graph import extract_model_visuals


def _dir_size_bytes(directory: Path) -> int:
    return sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())


def _safe_model_name(name: str) -> str:
    cleaned = name.strip()
    if (
        not cleaned
        or cleaned in {".", ".."}
        or "/" in cleaned
        or "\\" in cleaned
        or "\0" in cleaned
    ):
        raise ValueError(f"Invalid model name: {name!r}")
    return cleaned


@dataclass(frozen=True)
class VehicleModelManager:
    resource_settings: ResourceSettings

    @classmethod
    def build(cls) -> VehicleModelManager:
        return cls(resource_settings=ResourceSettings.build())

    def list_models(self) -> dict[str, Any]:
        gen_dir = self.resource_settings.generated_models_dir.resolve()
        items: list[dict[str, Any]] = []
        if gen_dir.is_dir():
            cache_resolver = ProductionCacheResolver()
            uri_rule = ProductionFuelUriRule()
            for entry in sorted(gen_dir.iterdir(), key=lambda p: p.name.lower()):
                if not entry.is_dir() or entry.name.startswith("."):
                    continue
                sdf_path = entry / "model.sdf"
                has_sdf = sdf_path.is_file()
                stat = sdf_path.stat() if has_sdf else entry.stat()
                has_3d = False
                if has_sdf:
                    try:
                        has_3d = bool(
                            extract_model_visuals(
                                entry,
                                source_models_dir=self.resource_settings.source_models_dir,
                                patched_models_dir=self.resource_settings.patched_models_dir,
                                generated_models_dir=gen_dir,
                                cache_resolver=cache_resolver,
                                uri_rule=uri_rule,
                            )
                        )
                    except Exception:
                        has_3d = False
                items.append(
                    {
                        "name": entry.name,
                        "has_sdf": has_sdf,
                        "has_3d": has_3d,
                        "has_config": (entry / "model.config").is_file(),
                        "size_bytes": _dir_size_bytes(entry),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                    }
                )
        return {
            "generated_models_dir": str(gen_dir),
            "generated_models": items,
        }

    def _resolve_generated_dir(self, model_name: str) -> Path:
        safe = _safe_model_name(model_name)
        root = self.resource_settings.generated_models_dir.resolve()
        target = (root / safe).resolve()
        if not target.is_relative_to(root) or not target.is_dir():
            raise FileNotFoundError(f"Generated vehicle model {safe!r} not found")
        return target

    def read_model_sdf(self, model_name: str) -> dict[str, Any]:
        model_dir = self._resolve_generated_dir(model_name)
        sdf_path = model_dir / "model.sdf"
        if not sdf_path.is_file():
            raise FileNotFoundError(f"model.sdf not found for {model_name!r}")
        content = sdf_path.read_text(encoding="utf-8", errors="replace")
        return {
            "scope": "generated",
            "name": model_dir.name,
            "size_bytes": sdf_path.stat().st_size,
            "content": content,
        }

    def delete_generated_model(self, model_name: str) -> dict[str, Any]:
        model_dir = self._resolve_generated_dir(model_name)
        shutil.rmtree(model_dir)
        return {"deleted": model_dir.name, **self.list_models()}

    def generate_fleet_models(self, *, world_key: str | None = None) -> dict[str, Any]:
        fleet = ProductionFleetPlanner(world_key=world_key)()
        builder = ProductionVehicleModelBuilder(s_resource=self.resource_settings)
        generated_names: list[str] = []
        for idx, member in enumerate(fleet, start=1):
            v = member.vehicle
            if v.airframe is None:
                raise ValueError(f"Vehicle #{idx}: airframe is required before generating")
            if not (v.namespace or "").strip():
                raise ValueError(f"Vehicle #{idx}: namespace is required before generating")
            out_dir = builder(vehicle=v)
            generated_names.append(out_dir.name)
        return {
            "generated": generated_names,
            **self.list_models(),
        }
