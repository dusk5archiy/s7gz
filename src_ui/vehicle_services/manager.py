from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src_sim.fuel.cache_resolvers.production import ProductionCacheResolver
from src_sim.fuel.uri_rules.production import ProductionFuelUriRule
from src_sim.settings.asset_ref import resolve_world_generated_models_dir
from src_sim.settings.resource import ResourceSettings
from src_sim.stage_fleet.fleet_planners.production import ProductionFleetPlanner
from src_sim.stage_fleet.production import prune_stale_world_generated_models
from src_sim.stage_vehicle.gz_model_name_transforms.production import (
    ProductionGzModelNameTransform,
)
from src_sim.stage_vehicle.production import ProductionVehicleModelBuilder
from src_ui.world_services.scene_graph import extract_model_visuals


def _dir_size_bytes(directory: Path) -> int:
    return sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())


def _safe_relative_model_path(rel_path: str) -> str:
    cleaned = rel_path.strip().lstrip("/")
    parts = [p for p in cleaned.split("/") if p]
    if (
        not parts
        or "\\" in cleaned
        or "\0" in cleaned
        or any(p in {".", ".."} for p in parts)
    ):
        raise ValueError(f"Invalid generated model path: {rel_path!r}")
    return "/".join(parts)


def _world_key_from_scope(scope_rel: str) -> str:
    if scope_rel.startswith("catalog/"):
        sub = scope_rel.removeprefix("catalog/")
        return f"catalog:{sub}.sdf"
    if scope_rel.startswith("path/"):
        return f"path:{scope_rel.removeprefix('path/')}"
    return scope_rel or "_default"


@dataclass(frozen=True)
class VehicleModelManager:
    resource_settings: ResourceSettings

    @classmethod
    def build(cls) -> VehicleModelManager:
        return cls(resource_settings=ResourceSettings.build())

    def list_models(self, *, active_world_key: str | None = None) -> dict[str, Any]:
        gen_root = self.resource_settings.generated_models_dir.resolve()
        gen_rel_root = self.resource_settings.generated_models_dir.as_posix()
        items: list[dict[str, Any]] = []
        worlds_map: dict[str, list[dict[str, Any]]] = {}

        if gen_root.is_dir():
            cache_resolver = ProductionCacheResolver()
            uri_rule = ProductionFuelUriRule()
            model_dirs = sorted(
                {sdf.parent for sdf in gen_root.rglob("model.sdf") if sdf.is_file()},
                key=lambda p: p.as_posix().lower(),
            )
            for entry in model_dirs:
                if not entry.is_dir() or not entry.resolve().is_relative_to(gen_root):
                    continue
                rel_path = entry.resolve().relative_to(gen_root).as_posix()
                parent_rel = (
                    entry.parent.resolve().relative_to(gen_root).as_posix()
                    if entry.parent.resolve() != gen_root
                    else ""
                )
                world_scope = parent_rel or "_root"
                world_key = _world_key_from_scope(parent_rel)
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
                                generated_models_dir=gen_root,
                                world_generated_models_dir=entry.parent,
                                cache_resolver=cache_resolver,
                                uri_rule=uri_rule,
                            )
                        )
                    except Exception:
                        has_3d = False
                item = {
                    "relative_path": rel_path,
                    "world_scope": world_scope,
                    "world_key": world_key,
                    "name": entry.name,
                    "has_sdf": has_sdf,
                    "has_3d": has_3d,
                    "has_config": (entry / "model.config").is_file(),
                    "size_bytes": _dir_size_bytes(entry),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                }
                items.append(item)
                worlds_map.setdefault(world_scope, []).append(item)

        worlds_list = [
            {
                "world_scope": scope,
                "world_key": _world_key_from_scope("" if scope == "_root" else scope),
                "dir_rel": (
                    f"{gen_rel_root}/{scope}" if scope != "_root" else gen_rel_root
                ),
                "models": models,
            }
            for scope, models in sorted(worlds_map.items(), key=lambda kv: kv[0].lower())
        ]
        return {
            "generated_models_dir": gen_rel_root,
            "active_world_key": active_world_key,
            "worlds": worlds_list,
            "generated_models": items,
        }

    def _resolve_generated_dir(self, relative_path: str) -> Path:
        safe = _safe_relative_model_path(relative_path)
        root = self.resource_settings.generated_models_dir.resolve()
        target = (root / safe).resolve()
        if not target.is_relative_to(root) or not target.is_dir():
            raise FileNotFoundError(f"Generated vehicle model {safe!r} not found")
        return target

    def read_model_sdf(self, relative_path: str) -> dict[str, Any]:
        model_dir = self._resolve_generated_dir(relative_path)
        sdf_path = model_dir / "model.sdf"
        if not sdf_path.is_file():
            raise FileNotFoundError(f"model.sdf not found for {relative_path!r}")
        content = sdf_path.read_text(encoding="utf-8", errors="replace")
        return {
            "scope": "generated",
            "relative_path": _safe_relative_model_path(relative_path),
            "name": model_dir.name,
            "size_bytes": sdf_path.stat().st_size,
            "content": content,
        }

    def delete_generated_model(
        self, relative_path: str, *, active_world_key: str | None = None
    ) -> dict[str, Any]:
        root = self.resource_settings.generated_models_dir.resolve()
        model_dir = self._resolve_generated_dir(relative_path)
        deleted_rel = model_dir.relative_to(root).as_posix()
        parent = model_dir.parent
        shutil.rmtree(model_dir)
        while parent != root and parent.is_relative_to(root):
            try:
                if any(parent.iterdir()):
                    break
                parent.rmdir()
                parent = parent.parent
            except OSError:
                break
        return {
            "deleted": deleted_rel,
            **self.list_models(active_world_key=active_world_key),
        }

    def generate_fleet_models(self, *, world_key: str | None = None) -> dict[str, Any]:
        fleet = ProductionFleetPlanner(world_key=world_key)()
        target_dir = resolve_world_generated_models_dir(
            world_key, resource=self.resource_settings
        )
        gz_name_transform = ProductionGzModelNameTransform()
        keep_names = {gz_name_transform(m.vehicle.namespace) for m in fleet}
        prune_stale_world_generated_models(target_dir, keep_names=keep_names)

        builder = ProductionVehicleModelBuilder(
            s_resource=self.resource_settings,
            world_key=world_key,
            models_dir=target_dir,
        )
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
            "world_key": world_key,
            "generated": generated_names,
            **self.list_models(active_world_key=world_key),
        }
