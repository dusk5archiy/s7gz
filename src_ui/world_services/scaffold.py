from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from s7dcls import StandardUncoercer

from src_sim.fuel.settings.world import WorldSettings
from src_sim.fuel.world_dependency_syncers.production import (
    ProductionWorldDependencySyncer,
)
from src_sim.settings.asset_ref import asset_ref_to_key
from src_sim.settings.resource import ResourceSettings
from src_sim.stage_fleet.settings import Settings as FleetSettings
from src_sim.stage_world_sdf.source_world_sdf_emitters.settings import (
    Settings as SourceWorldSettings,
)

from ..providers import PROVIDERS, AssetProviderSpec, get_provider, provider_from_rel_path
from ..px4_sync import sync_px4_gazebo_repo
from ..settings_services.protocol import SettingsServiceProtocol
from ..thumbnail_utils import find_world_thumbnail_url
from .protocol import WorldScope, WorldServiceProtocol


def _resolve_world_file(base_dir: Path, relative_path: str) -> Path:
    if not relative_path or relative_path.startswith("/") or "\\" in relative_path:
        raise ValueError(f"Invalid world path: {relative_path!r}")
    base_resolved = base_dir.resolve()
    target = (base_resolved / relative_path).resolve()
    if not target.is_relative_to(base_resolved) or target == base_resolved:
        raise ValueError(f"Path escapes base directory: {relative_path!r}")
    if target.suffix.lower() != ".sdf":
        raise ValueError(f"Expected .sdf file, got: {relative_path!r}")
    return target


def _scan_provider_worlds(
    provider_dir: Path,
    *,
    provider: str,
    root_dir: Path,
    source_models_dir: Path,
) -> list[dict[str, Any]]:
    if not provider_dir.is_dir():
        return []
    root_resolved = root_dir.resolve()
    prov_resolved = provider_dir.resolve()
    items: list[dict[str, Any]] = []
    for path in sorted(prov_resolved.rglob("*.sdf")):
        if not path.is_file():
            continue
        stat = path.stat()
        rel_from_root = path.relative_to(root_resolved).as_posix()
        display_path = path.relative_to(prov_resolved).as_posix()
        has_3d = False
        try:
            sdf_txt = path.read_text(encoding="utf-8", errors="replace")
            has_3d = "<include" in sdf_txt or ("<visual" in sdf_txt and "<geometry" in sdf_txt)
        except OSError:
            has_3d = False
        thumbnail_url = (
            find_world_thumbnail_url(rel_from_root, source_models_dir=source_models_dir)
            if provider == "fuel"
            else None
        )
        items.append(
            {
                "provider": provider,
                "relative_path": rel_from_root,
                "display_path": display_path,
                "name": path.stem,
                "has_3d": has_3d,
                "thumbnail_url": thumbnail_url,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        )
    return items


def _extract_sdf_world_name(content: str) -> str | None:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None
    world_el = root.find("world")
    if world_el is not None:
        return world_el.attrib.get("name")
    if root.tag == "world":
        return root.attrib.get("name")
    return None


@dataclass(kw_only=True, frozen=True)
class ScaffoldWorldService(WorldServiceProtocol):
    settings_service: SettingsServiceProtocol
    resource_settings_factory: Callable[[], ResourceSettings]
    world_settings_factory: Callable[[], WorldSettings]
    fuel_world_emitter_factory: Callable[[], Path | None]
    patched_world_emitter_factory: Callable[[], Path]
    providers: dict[str, AssetProviderSpec] = field(default_factory=lambda: dict(PROVIDERS))

    def _scope_dir(self, scope: WorldScope) -> Path:
        res = self.resource_settings_factory()
        if scope == "source":
            return res.source_worlds_dir
        if scope == "patched":
            return res.patched_worlds_dir
        raise ValueError(f"Unknown world scope: {scope!r}")

    def list_worlds(self) -> dict[str, Any]:
        self.settings_service.apply_overrides()
        res = self.resource_settings_factory()
        active = self.world_settings_factory()
        src_settings = SourceWorldSettings.build()
        fleet_worlds = FleetSettings.build().worlds
        cwd = Path.cwd().resolve()
        source_dir = res.source_worlds_dir.resolve()
        patched_dir = res.patched_worlds_dir.resolve()
        source_rel_root = (
            source_dir.relative_to(cwd).as_posix()
            if source_dir.is_relative_to(cwd)
            else str(source_dir)
        )
        patched_rel_root = (
            patched_dir.relative_to(cwd).as_posix()
            if patched_dir.is_relative_to(cwd)
            else str(patched_dir)
        )

        providers_payload: dict[str, dict[str, Any]] = {}
        for key, spec in self.providers.items():
            prov_src = source_dir / key
            prov_patched = patched_dir / key
            patched_items = _scan_provider_worlds(
                prov_patched,
                provider=key,
                root_dir=patched_dir,
                source_models_dir=res.source_models_dir,
            )
            patched_rels = {w["relative_path"] for w in patched_items}
            for w in patched_items:
                w["is_patched"] = True
                w_key = f"catalog:{w['relative_path']}"
                w["world_key"] = w_key
                w["world_path"] = f"{source_rel_root}/{w['relative_path']}"
                w["fleet_vehicle_count"] = (
                    len(fleet_worlds[w_key].vehicles) if w_key in fleet_worlds else 0
                )
            source_items = _scan_provider_worlds(
                prov_src,
                provider=key,
                root_dir=source_dir,
                source_models_dir=res.source_models_dir,
            )
            for w in source_items:
                w["is_patched"] = w["relative_path"] in patched_rels
                w_key = f"catalog:{w['relative_path']}"
                w["world_key"] = w_key
                w["world_path"] = f"{source_rel_root}/{w['relative_path']}"
                w["fleet_vehicle_count"] = (
                    len(fleet_worlds[w_key].vehicles) if w_key in fleet_worlds else 0
                )
            providers_payload[key] = {
                "key": spec.key,
                "label": spec.label,
                "supports_download": spec.supports_download,
                "supports_sync": spec.supports_sync,
                "can_delete_source": spec.can_delete_source,
                "source_dir": str(prov_src),
                "source_rel_dir": f"{source_rel_root}/{key}",
                "patched_dir": str(prov_patched),
                "patched_rel_dir": f"{patched_rel_root}/{key}",
                "source_worlds": source_items,
                "patched_worlds": patched_items,
            }

        uncoercer = StandardUncoercer.Args().build()
        return {
            "source_dir": str(source_dir),
            "source_rel_dir": source_rel_root,
            "patched_dir": str(patched_dir),
            "patched_rel_dir": patched_rel_root,
            "active": {
                "world_name": active.world_name,
                "world_url": active.world_url,
                "active_world": uncoercer(value=src_settings.active_world),
                "active_world_key": asset_ref_to_key(src_settings.active_world),
                "world_file": str(src_settings.world_file)
                if src_settings.world_file is not None
                else None,
            },
            "providers": providers_payload,
        }

    def read_world(
        self, *, scope: WorldScope, relative_path: str
    ) -> dict[str, Any]:
        self.settings_service.apply_overrides()
        base_dir = self._scope_dir(scope)
        target = _resolve_world_file(base_dir, relative_path)
        if not target.is_file():
            raise FileNotFoundError(f"World file not found: {relative_path!r}")
        content = target.read_text(encoding="utf-8")
        stat = target.stat()
        return {
            "scope": scope,
            "relative_path": relative_path,
            "size_bytes": stat.st_size,
            "world_name": _extract_sdf_world_name(content),
            "content": content,
        }

    def delete_world(
        self, *, scope: WorldScope, relative_path: str
    ) -> dict[str, Any]:
        self.settings_service.apply_overrides()
        base_dir = self._scope_dir(scope)
        target = _resolve_world_file(base_dir, relative_path)
        if not target.is_file():
            raise FileNotFoundError(f"World file not found: {relative_path!r}")
        target.unlink()
        return {"deleted": relative_path, "scope": scope}

    def download_world(
        self,
        *,
        world_name: str | None = None,
        world_url: str | None = None,
        select: bool = True,
    ) -> dict[str, Any]:
        cleaned_name = world_name.strip() if world_name else None
        cleaned_url = world_url.strip() if world_url else None
        if not cleaned_name and not cleaned_url:
            raise ValueError("Provide either world_name or world_url")

        self.settings_service.apply_overrides()
        prev_name = os.environ.get("__SIM__FUEL__WORLD_NAME")
        prev_url = os.environ.get("__SIM__FUEL__WORLD_URL")

        if cleaned_name is not None:
            os.environ["__SIM__FUEL__WORLD_NAME"] = cleaned_name
        else:
            os.environ.pop("__SIM__FUEL__WORLD_NAME", None)
        if cleaned_url is not None:
            os.environ["__SIM__FUEL__WORLD_URL"] = cleaned_url
        else:
            os.environ.pop("__SIM__FUEL__WORLD_URL", None)

        try:
            out_path = self.fuel_world_emitter_factory()
        finally:
            if prev_name is None:
                os.environ.pop("__SIM__FUEL__WORLD_NAME", None)
            else:
                os.environ["__SIM__FUEL__WORLD_NAME"] = prev_name
            if prev_url is None:
                os.environ.pop("__SIM__FUEL__WORLD_URL", None)
            else:
                os.environ["__SIM__FUEL__WORLD_URL"] = prev_url

        if out_path is None:
            raise RuntimeError("Fuel world emitter returned None")
        res = self.resource_settings_factory()
        out_resolved = out_path.resolve()
        rel = (
            out_resolved.relative_to(res.source_worlds_dir.resolve()).as_posix()
            if out_resolved.is_relative_to(res.source_worlds_dir.resolve())
            else out_path.name
        )
        if select:
            self.settings_service.update(
                updates={
                    "__SIM__ACTIVE_WORLD": {"kind": "catalog", "relative_path": rel},
                    "__SIM__FUEL__WORLD_NAME": None,
                    "__SIM__FUEL__WORLD_URL": None,
                }
            )
        return {
            "exported_sdf": str(out_path),
            "relative_path": rel,
        }

    def prepare_world(self) -> dict[str, Any]:
        self.settings_service.apply_overrides()
        out_sdf = self.patched_world_emitter_factory()
        return {"patched_world_sdf": str(out_sdf)}

    def patch_world(self, *, relative_path: str) -> dict[str, Any]:
        self.settings_service.apply_overrides()
        res = self.resource_settings_factory()
        spec, _ = provider_from_rel_path(relative_path)
        target = _resolve_world_file(res.source_worlds_dir, relative_path)
        if not target.is_file():
            raise FileNotFoundError(f"Source world file not found: {relative_path!r}")

        if spec.key == "px4":
            text = target.read_text(encoding="utf-8", errors="replace")
            if "https://fuel." in text:
                ProductionWorldDependencySyncer()(x=target)

        prev_active_world = os.environ.get("__SIM__ACTIVE_WORLD")
        os.environ["__SIM__ACTIVE_WORLD"] = json.dumps(
            {"kind": "catalog", "relative_path": relative_path}
        )
        try:
            out_sdf = self.patched_world_emitter_factory()
        finally:
            if prev_active_world is None:
                os.environ.pop("__SIM__ACTIVE_WORLD", None)
            else:
                os.environ["__SIM__ACTIVE_WORLD"] = prev_active_world

        rel = (
            out_sdf.resolve()
            .relative_to(res.patched_worlds_dir.resolve())
            .as_posix()
            if out_sdf.resolve().is_relative_to(res.patched_worlds_dir.resolve())
            else out_sdf.name
        )
        return {"patched_world_sdf": str(out_sdf), "relative_path": rel}

    def sync_provider(self, *, provider: str) -> dict[str, Any]:
        self.settings_service.apply_overrides()
        spec = get_provider(provider)
        if not spec.supports_sync:
            raise ValueError(f"Provider {provider!r} does not support sync")
        res = self.resource_settings_factory()
        if spec.key == "px4":
            sync_px4_gazebo_repo(res)
        return self.list_worlds()


__all__ = ["ScaffoldWorldService"]
