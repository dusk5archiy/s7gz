from __future__ import annotations

import os
import posixpath
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, unquote

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from s7dcls import (
    StandardTypeDescriber,
    StandardUncoercer,
    StrictTypeDescriberProtocol,
    StrictUncoercerProtocol,
)

from src_sim.fuel.cache_resolvers.production import ProductionCacheResolver
from src_sim.fuel.settings.world import WorldSettings
from src_sim.fuel.uri_rules.production import ProductionFuelUriRule
from src_sim.fuel.world_asset_ensurers.standard import StandardFuelUrlParser
from src_sim.fuel.world_url_emitters.settings import Settings as WorldUrlSettings
from src_sim.settings.asset_ref import (
    AssetRef,
    CatalogAssetRef,
    PathAssetRef,
    asset_ref_from_key,
    asset_ref_to_key,
    resolve_model_asset_path,
    resolve_world_asset_path,
    resolve_world_generated_models_dir,
)
from src_sim.settings.resource import ResourceSettings
from src_sim.stage_fleet.base_station import find_base_station_pose_from_file
from src_sim.stage_fleet.fleet_planners.production import ProductionFleetPlanner
from src_sim.stage_fleet.settings import (
    Settings as FleetSettings,
    WorldFleetConfig,
    resolve_world_fleet_key,
)
from src_sim.stage_world_sdf.source_world_sdf_emitters.settings import (
    Settings as SourceWorldSettings,
)
from src_sim.stage_vehicle.attachments.mechanism.flashlight import (
    DEFAULT_FLASHLIGHT_POSE,
    FlashlightApplier,
)
from src_sim.stage_vehicle.devices.mechanism.scan_lidar import (
    DEFAULT_SCAN_LIDAR_POSE,
    ScanLidarApplier,
)
from src_sim.stage_vehicle.gz_model_name_transforms.production import (
    ProductionGzModelNameTransform,
)
from src_sim.stage_vehicle.models import AttachmentSpec, DeviceSpec, VehicleSpec

from .env_loaders.bash import apply_env_from_script
from .fuel_tasks import (
    FuelTaskBusyError,
    acquire_fuel_operation,
    get_fuel_task,
    get_fuel_terminal_state,
    start_fuel_task,
)
from .model_services.manager import ModelManager
from .override_stores.production import ProductionOverrideStore
from .settings_services.production import ProductionSettingsService
from .settings_services.protocol import SettingsServiceProtocol
from .thumbnail_utils import (
    dae_to_geometry_glb,
    find_model_thumbnail_url,
    find_world_thumbnail_url,
    strip_dae_images,
    strip_glb_textures,
)
from .validation import validate_settings_updates
from .vehicle_services.manager import VehicleModelManager
from .world_services.production import ProductionWorldService
from .world_services.protocol import WorldScope, WorldServiceProtocol
from .world_services.scene_graph import (
    extract_model_visuals,
    extract_world_scene,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SIM_ENV_SCRIPT = _REPO_ROOT / "docker_sim" / "host--env.sh"


@lru_cache(maxsize=1)
def ensure_sim_env() -> dict[str, str]:
    return apply_env_from_script(_SIM_ENV_SCRIPT, cwd=_REPO_ROOT)


ensure_sim_env()

app = FastAPI(title="s7gz UI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3057", "http://127.0.0.1:3057"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_settings_service() -> SettingsServiceProtocol:
    return ProductionSettingsService()


@lru_cache(maxsize=1)
def get_world_service() -> WorldServiceProtocol:
    return ProductionWorldService(settings_service=get_settings_service())


@lru_cache(maxsize=1)
def get_uncoercer() -> StrictUncoercerProtocol:
    return StandardUncoercer.Args().build()


@lru_cache(maxsize=1)
def get_type_describer() -> StrictTypeDescriberProtocol:
    return StandardTypeDescriber.Args(include_docstrings=True).build()


class SettingsUpdateRequest(BaseModel):
    updates: dict[str, Any]


class WorldDownloadRequest(BaseModel):
    world_name: str | None = None
    world_url: str | None = None
    select: bool = True


class WorldPatchRequest(BaseModel):
    relative_path: str


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return {"groups": get_settings_service().list_groups()}


@app.get("/api/settings/overrides")
def get_settings_overrides() -> dict[str, Any]:
    store = ProductionOverrideStore()
    return {
        "path": str(store.s_common.ui_json_file),
        "overrides": store.load(),
    }


@app.put("/api/settings")
def put_settings(body: SettingsUpdateRequest) -> dict[str, Any]:
    errors = validate_settings_updates(body.updates)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))
    service = get_settings_service()
    try:
        merged = service.update(updates=body.updates)
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"saved": merged, "groups": service.list_groups()}


@app.delete("/api/settings/overrides/{env_key}")
def delete_setting_override(env_key: str) -> dict[str, Any]:
    service = get_settings_service()
    remaining = service.clear_overrides(keys=[env_key])
    return {"saved": remaining, "groups": service.list_groups()}


def _resolve_local_source_world(*, auto_patch: bool = False) -> Path | None:
    src_settings = SourceWorldSettings.build()
    res = ResourceSettings.build()
    if src_settings.world_file is not None and src_settings.world_file.is_file():
        wf_resolved = src_settings.world_file.resolve()
        source_worlds_dir = res.source_worlds_dir.resolve()
        if wf_resolved.is_relative_to(source_worlds_dir):
            rel = wf_resolved.relative_to(source_worlds_dir).as_posix()
            patched = res.patched_worlds_dir / rel
            if patched.is_file():
                return patched
            if auto_patch:
                try:
                    result = get_world_service().patch_world(relative_path=rel)
                    prepared = Path(result["patched_world_sdf"])
                    if prepared.is_file():
                        return prepared
                except Exception:
                    pass
        return src_settings.world_file
    w_settings = WorldSettings.build()
    url_settings = WorldUrlSettings.build()

    owner: str | None = None
    name: str | None = None
    if w_settings.world_url and w_settings.world_url.strip():
        ref = StandardFuelUrlParser()(w_settings.world_url)
        owner, name = ref.owner, ref.name
    elif w_settings.world_name and w_settings.world_name.strip():
        raw = w_settings.world_name.strip()
        if "/" in raw:
            owner, name = (p.strip() for p in raw.split("/", 1))
        else:
            owner, name = url_settings.default_owner, raw

    if owner and name:
        patched = res.patched_worlds_of("fuel") / owner / f"{name}.sdf"
        if patched.is_file():
            return patched
        if auto_patch:
            try:
                result = get_world_service().prepare_world()
                prepared = Path(result["patched_world_sdf"])
                if prepared.is_file():
                    return prepared
            except Exception:
                pass
        source = res.source_worlds_of("fuel") / owner / f"{name}.sdf"
        return source if source.is_file() else None

    empty_path = src_settings.empty_world_file
    return empty_path if empty_path.is_file() else None


def _resolve_active_world_ref() -> AssetRef | None:
    src_settings = SourceWorldSettings.build()
    if src_settings.active_world is not None:
        return src_settings.active_world

    w_settings = WorldSettings.build()
    url_settings = WorldUrlSettings.build()
    owner: str | None = None
    name: str | None = None
    if w_settings.world_url and w_settings.world_url.strip():
        ref = StandardFuelUrlParser()(w_settings.world_url)
        owner, name = ref.owner, ref.name
    elif w_settings.world_name and w_settings.world_name.strip():
        raw = w_settings.world_name.strip()
        if "/" in raw:
            owner, name = (p.strip() for p in raw.split("/", 1))
        else:
            owner, name = url_settings.default_owner, raw
    if owner and name:
        return CatalogAssetRef(relative_path=f"fuel/{owner}/{name}.sdf")
    return None


def _resolve_active_world_key() -> str | None:
    return asset_ref_to_key(_resolve_active_world_ref())


def _resolve_world_ref_to_file(
    ref: AssetRef,
    *,
    prefer_patched: bool = True,
) -> Path | None:
    res = ResourceSettings.build()
    if isinstance(ref, CatalogAssetRef):
        try:
            target = resolve_world_asset_path(
                ref, resource=res, prefer_patched=prefer_patched
            ).resolve()
        except ValueError:
            return None
        allowed = (res.source_worlds_dir.resolve(), res.patched_worlds_dir.resolve())
        if any(target.is_relative_to(root) for root in allowed) and target.is_file():
            return target
        return None

    cwd = Path.cwd().resolve()
    raw_path = ref.path.expanduser()
    target = raw_path.resolve() if raw_path.is_absolute() else (cwd / raw_path).resolve()
    if target.is_relative_to(cwd) and target.is_file():
        return target
    return None


@app.get("/api/fleet/preview")
def fleet_preview(
    world_key: str | None = None,
    world_path: str | None = None,
) -> dict[str, Any]:
    get_settings_service().apply_overrides()
    res = ResourceSettings.build()
    active_world_ref = _resolve_active_world_ref()
    active_world_key = asset_ref_to_key(active_world_ref)

    requested = (world_key or world_path or "").strip()
    if requested:
        selected_ref = (
            asset_ref_from_key(requested)
            if requested.startswith(("catalog:", "path:"))
            else asset_ref_from_key(resolve_world_fleet_key(requested, resource=res))
        )
        resolved_key = asset_ref_to_key(selected_ref)
        source_world_path = (
            _resolve_world_ref_to_file(selected_ref, prefer_patched=True)
            if selected_ref is not None
            else None
        )
    else:
        selected_ref = active_world_ref
        resolved_key = active_world_key
        source_world_path = (
            _resolve_world_ref_to_file(active_world_ref, prefer_patched=True)
            if active_world_ref is not None
            else _resolve_local_source_world(auto_patch=False)
        )

    base_station = (
        find_base_station_pose_from_file(source_world_path)
        if source_world_path is not None
        else None
    )

    s_fleet = FleetSettings.build()
    has_saved_fleet = bool(resolved_key and resolved_key in s_fleet.worlds)
    fleet_cfg = s_fleet.for_world(resolved_key)
    planner = ProductionFleetPlanner(
        world_key=resolved_key,
        fleet_config=fleet_cfg,
        s_fleet=s_fleet,
        base_station_pose=base_station,
    )
    members = planner()
    effective_center = planner.resolve_center()
    uncoercer = get_uncoercer()
    gz_name_transform = ProductionGzModelNameTransform()
    return {
        "world_ref": uncoercer(value=selected_ref),
        "active_world_ref": uncoercer(value=active_world_ref),
        "world_key": resolved_key,
        "active_world_key": active_world_key,
        "has_saved_fleet": has_saved_fleet,
        "fleet_config": uncoercer(value=fleet_cfg),
        "default_fleet_config": uncoercer(value=WorldFleetConfig()),
        "members": [
            {
                **uncoercer(value=m),
                "gz_model_name": gz_name_transform(m.vehicle.namespace),
            }
            for m in members
        ],
        "base_station": uncoercer(value=base_station),
        "effective_center": uncoercer(value=effective_center),
        "source_world": str(source_world_path) if source_world_path else None,
    }


def _discover_airframes() -> list[str]:
    """Return catalog relative paths (under source_models/) for all models with model.sdf."""
    res = ResourceSettings.build()
    src_root = res.source_models_dir.resolve()
    if not src_root.is_dir():
        return []
    paths: list[str] = []
    for sdf in sorted(src_root.rglob("model.sdf"), key=lambda p: p.as_posix().lower()):
        if sdf.is_file() and sdf.resolve().is_relative_to(src_root):
            paths.append(sdf.resolve().relative_to(src_root).as_posix())
    return paths


def _default_x500_airframe() -> AssetRef:
    return CatalogAssetRef(relative_path="px4/x500/model.sdf")


@app.get("/api/vehicles/catalog")
def vehicle_catalog() -> dict[str, Any]:
    uncoercer = get_uncoercer()
    describer = get_type_describer()
    flashlight_applier = FlashlightApplier()
    lidar_applier = ScanLidarApplier()
    default_x500 = _default_x500_airframe()

    return {
        "airframes": _discover_airframes(),
        "attachments": [
            {
                "kind": "flashlight",
                "default_slot": "flashlight",
                "default_pose": uncoercer(value=DEFAULT_FLASHLIGHT_POSE),
                "default_params": uncoercer(value=flashlight_applier),
                "params_schema": describer(dtype=FlashlightApplier)["fields"],
            }
        ],
        "devices": [
            {
                "kind": "scan_lidar",
                "default_name": "scan_lidar",
                "default_pose": uncoercer(value=DEFAULT_SCAN_LIDAR_POSE),
                "default_params": uncoercer(value=lidar_applier),
                "params_schema": describer(dtype=ScanLidarApplier)["fields"],
            }
        ],
        "presets": [
            {
                "id": "empty",
                "label": "Blank Vehicle",
                "description": "Empty vehicle without airframe or equipment",
                "vehicle": uncoercer(
                    value=VehicleSpec(namespace="", airframe=None)
                ),
            },
            {
                "id": "x500",
                "label": "x500 (Base)",
                "description": "Standard x500 quadrotor with no extra payload",
                "vehicle": uncoercer(
                    value=VehicleSpec(namespace="", airframe=default_x500)
                ),
            },
            {
                "id": "x500_flashlight",
                "label": "x500 + Flashlight",
                "description": "x500 equipped with a spotlight attachment",
                "vehicle": uncoercer(
                    value=VehicleSpec(
                        namespace="",
                        airframe=default_x500,
                        attachments=(
                            AttachmentSpec(slot="flashlight", kind="flashlight"),
                        ),
                    )
                ),
            },
            {
                "id": "x500_lidar",
                "label": "x500 + Scan LiDAR",
                "description": "x500 equipped with a 3D scanning LiDAR",
                "vehicle": uncoercer(
                    value=VehicleSpec(
                        namespace="",
                        airframe=default_x500,
                        devices=(DeviceSpec(name="scan_lidar", kind="scan_lidar"),),
                    )
                ),
            },
            {
                "id": "x500_recon",
                "label": "x500 (Flashlight + LiDAR)",
                "description": "x500 equipped with both flashlight and scan LiDAR",
                "vehicle": uncoercer(
                    value=VehicleSpec(
                        namespace="",
                        airframe=default_x500,
                        attachments=(
                            AttachmentSpec(slot="flashlight", kind="flashlight"),
                        ),
                        devices=(DeviceSpec(name="scan_lidar", kind="scan_lidar"),),
                    )
                ),
            },
        ],
    }


@app.get("/api/vehicles/models")
def list_vehicle_models() -> dict[str, Any]:
    get_settings_service().apply_overrides()
    return VehicleModelManager.build().list_models(
        active_world_key=_resolve_active_world_key()
    )


@app.get("/api/vehicles/models/generated/{model_name:path}")
def read_generated_vehicle_model(model_name: str) -> dict[str, Any]:
    get_settings_service().apply_overrides()
    try:
        return VehicleModelManager.build().read_model_sdf(model_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/vehicles/models/generated/{model_name:path}")
def delete_generated_vehicle_model(model_name: str) -> dict[str, Any]:
    get_settings_service().apply_overrides()
    try:
        with acquire_fuel_operation(f"Delete generated vehicle: {model_name}"):
            return VehicleModelManager.build().delete_generated_model(
                model_name, active_world_key=_resolve_active_world_key()
            )
    except FuelTaskBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class FuelModelDownloadRequest(BaseModel):
    model_name: str | None = None
    model_url: str | None = None


class FuelTaskStartRequest(BaseModel):
    action: Literal[
        "world_download",
        "world_patch",
        "world_prepare",
        "world_delete",
        "world_provider_sync",
        "model_download",
        "model_patch",
        "model_redownload",
        "model_delete",
        "model_provider_sync",
        "vehicle_generate",
        "vehicle_delete",
    ]
    provider: str | None = None
    world_name: str | None = None
    world_url: str | None = None
    select: bool = True
    relative_path: str | None = None
    model_name: str | None = None
    model_url: str | None = None
    scope: Literal["source", "patched", "generated"] = "source"


@app.post("/api/fuel-tasks/start")
def start_fuel_background_task(body: FuelTaskStartRequest) -> dict[str, str]:
    get_settings_service().apply_overrides()
    try:
        if body.action == "world_download":
            target = body.world_name or body.world_url or "world"
            task_id = start_fuel_task(
                f"Download world: {target}",
                lambda: get_world_service().download_world(
                    world_name=body.world_name,
                    world_url=body.world_url,
                    select=body.select,
                ),
            )
        elif body.action == "world_patch":
            if not body.relative_path:
                raise HTTPException(status_code=400, detail="relative_path is required")
            rel = body.relative_path
            task_id = start_fuel_task(
                f"Patch world: {rel}",
                lambda: get_world_service().patch_world(relative_path=rel),
            )
        elif body.action == "world_provider_sync":
            prov = (body.provider or "px4").strip()
            task_id = start_fuel_task(
                f"Sync {prov} worlds & models",
                lambda: get_world_service().sync_provider(provider=prov),
            )
        elif body.action == "world_prepare":
            task_id = start_fuel_task(
                "Prepare / Patch active world",
                lambda: get_world_service().prepare_world(),
            )
        elif body.action == "world_delete":
            if not body.relative_path:
                raise HTTPException(status_code=400, detail="relative_path is required")
            if body.scope not in ("source", "patched"):
                raise HTTPException(status_code=400, detail="Invalid world scope")
            rel = body.relative_path
            sc: WorldScope = body.scope
            task_id = start_fuel_task(
                f"Delete {sc} world: {rel}",
                lambda: get_world_service().delete_world(scope=sc, relative_path=rel),
            )
        elif body.action == "model_download":
            target = body.model_name or body.model_url or "model"
            task_id = start_fuel_task(
                f"Download model: {target}",
                lambda: ModelManager.build().download_model(
                    model_url=body.model_url,
                    model_name=body.model_name,
                ),
            )
        elif body.action == "model_patch":
            if not body.relative_path:
                raise HTTPException(status_code=400, detail="relative_path is required")
            rel = body.relative_path
            task_id = start_fuel_task(
                f"Patch model: {rel}",
                lambda: ModelManager.build().patch_model(rel),
            )
        elif body.action == "model_redownload":
            if not body.relative_path:
                raise HTTPException(status_code=400, detail="relative_path is required")
            if body.scope not in ("source", "patched"):
                raise HTTPException(status_code=400, detail="Invalid model scope")
            rel = body.relative_path
            msc: Literal["source", "patched"] = body.scope
            task_id = start_fuel_task(
                f"Re-download model: {rel}",
                lambda: ModelManager.build().redownload_model(rel, scope=msc),
            )
        elif body.action == "model_delete":
            if not body.relative_path:
                raise HTTPException(status_code=400, detail="relative_path is required")
            if body.scope not in ("source", "patched"):
                raise HTTPException(status_code=400, detail="Invalid model scope")
            rel = body.relative_path
            msc_del: Literal["source", "patched"] = body.scope
            task_id = start_fuel_task(
                f"Delete {msc_del} model: {rel}",
                lambda: ModelManager.build().delete_model(rel, scope=msc_del),
            )
        elif body.action == "model_provider_sync":
            prov = (body.provider or "px4").strip()
            task_id = start_fuel_task(
                f"Sync {prov} models & worlds",
                lambda: ModelManager.build().sync_provider(provider=prov),
            )
        elif body.action == "vehicle_generate":
            world_key = _resolve_active_world_key()
            task_id = start_fuel_task(
                "Generate fleet vehicle models",
                lambda: VehicleModelManager.build().generate_fleet_models(
                    world_key=world_key
                ),
            )
        elif body.action == "vehicle_delete":
            if not body.model_name:
                raise HTTPException(status_code=400, detail="model_name is required")
            vname = body.model_name
            active_wk = _resolve_active_world_key()
            task_id = start_fuel_task(
                f"Delete generated vehicle: {vname}",
                lambda: VehicleModelManager.build().delete_generated_model(
                    vname, active_world_key=active_wk
                ),
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")
    except FuelTaskBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"task_id": task_id}


@app.get("/api/fuel-tasks/current")
def read_current_fuel_terminal_state() -> dict[str, Any]:
    return get_fuel_terminal_state()


@app.get("/api/fuel-tasks/{task_id}")
def read_fuel_background_task(task_id: str) -> dict[str, Any]:
    task = get_fuel_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/api/models")
def list_models() -> dict[str, Any]:
    get_settings_service().apply_overrides()
    return ModelManager.build().list_models()


@app.post("/api/models/download")
def download_model(body: FuelModelDownloadRequest) -> dict[str, Any]:
    get_settings_service().apply_overrides()
    try:
        with acquire_fuel_operation(f"Download model: {body.model_name or body.model_url or 'model'}"):
            return ModelManager.build().download_model(
                model_url=body.model_url,
                model_name=body.model_name,
            )
    except FuelTaskBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/models/patch/{relative_path:path}")
def patch_model(relative_path: str) -> dict[str, Any]:
    get_settings_service().apply_overrides()
    try:
        with acquire_fuel_operation(f"Patch model: {relative_path}"):
            return ModelManager.build().patch_model(relative_path)
    except FuelTaskBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/models/redownload/{relative_path:path}")
def redownload_model(
    relative_path: str, scope: Literal["source", "patched"] = "source"
) -> dict[str, Any]:
    get_settings_service().apply_overrides()
    try:
        with acquire_fuel_operation(f"Re-download model: {relative_path}"):
            return ModelManager.build().redownload_model(relative_path, scope=scope)
    except FuelTaskBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/models/visuals/{relative_path:path}")
def get_model_visuals(
    relative_path: str, scope: Literal["source", "patched"] = "source"
) -> dict[str, Any]:
    get_settings_service().apply_overrides()
    res = ResourceSettings.build()
    try:
        model_dir = ModelManager.build()._resolve_model_dir(
            relative_path, scope=scope
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    visuals = extract_model_visuals(
        model_dir,
        source_models_dir=res.source_models_dir,
        patched_models_dir=res.patched_models_dir,
        generated_models_dir=res.generated_models_dir,
        cache_resolver=ProductionCacheResolver(),
        uri_rule=ProductionFuelUriRule(),
        uncoercer=get_uncoercer(),
    )
    thumbnail_url = find_model_thumbnail_url(
        model_dir,
        source_models_dir=res.source_models_dir,
        patched_models_dir=res.patched_models_dir,
        relative_path=relative_path,
    )
    return {
        "scope": scope,
        "relative_path": relative_path,
        "thumbnail_url": thumbnail_url,
        "visuals": visuals,
    }


@app.get("/api/models/sdf/{relative_path:path}")
def read_model_sdf(
    relative_path: str, scope: Literal["source", "patched"] = "source"
) -> dict[str, Any]:
    get_settings_service().apply_overrides()
    try:
        return ModelManager.build().read_model_sdf(relative_path, scope=scope)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/models/{relative_path:path}")
def delete_model(
    relative_path: str, scope: Literal["source", "patched"] = "source"
) -> dict[str, Any]:
    get_settings_service().apply_overrides()
    try:
        with acquire_fuel_operation(f"Delete {scope} model: {relative_path}"):
            return ModelManager.build().delete_model(relative_path, scope=scope)
    except FuelTaskBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/vehicles/generate")
def generate_fleet_vehicle_models(world_path: str | None = None) -> dict[str, Any]:
    get_settings_service().apply_overrides()
    world_key = (
        resolve_world_fleet_key(world_path)
        if world_path and world_path.strip()
        else _resolve_active_world_key()
    )
    try:
        with acquire_fuel_operation("Generate fleet vehicle models"):
            return VehicleModelManager.build().generate_fleet_models(
                world_key=world_key
            )
    except FuelTaskBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/vehicles/airframe-visuals/{airframe:path}")
def get_airframe_visuals(airframe: str) -> dict[str, Any]:
    raw = airframe.strip()
    if not raw or "\\" in raw:
        raise HTTPException(status_code=400, detail="Invalid airframe reference")
    get_settings_service().apply_overrides()
    res = ResourceSettings.build()
    cwd = Path.cwd().resolve()

    ref = asset_ref_from_key(raw)
    if ref is None:
        raise HTTPException(status_code=400, detail="Invalid airframe reference")
    try:
        resolved = resolve_model_asset_path(ref, resource=res, prefer_patched=True).resolve()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    allowed_roots = (
        res.patched_models_dir.resolve(),
        res.source_models_dir.resolve(),
        cwd,
    )
    if not any(resolved.is_relative_to(r) for r in allowed_roots) or not resolved.exists():
        raise HTTPException(status_code=404, detail=f"Airframe SDF not found: {raw}")

    visuals = extract_model_visuals(
        resolved,
        source_models_dir=res.source_models_dir,
        patched_models_dir=res.patched_models_dir,
        generated_models_dir=res.generated_models_dir,
        cache_resolver=ProductionCacheResolver(),
        uri_rule=ProductionFuelUriRule(),
        uncoercer=get_uncoercer(),
    )
    return {"airframe": raw, "visuals": visuals}


@app.get("/api/worlds")
def list_worlds() -> dict[str, Any]:
    return get_world_service().list_worlds()


@app.get("/api/worlds/scene")
def get_world_scene(
    relative_path: str | None = None,
    scope: WorldScope = "patched",
    world_key: str | None = None,
    world_path: str | None = None,
    exclude_fleet: bool = False,
) -> dict[str, Any]:
    get_settings_service().apply_overrides()
    res = ResourceSettings.build()
    requested = (world_key or world_path or "").strip()
    if requested:
        ref = (
            asset_ref_from_key(requested)
            if requested.startswith(("catalog:", "path:"))
            else asset_ref_from_key(resolve_world_fleet_key(requested, resource=res))
        )
        source_world_path: Path | None = (
            _resolve_world_ref_to_file(ref, prefer_patched=True)
            if ref is not None
            else None
        )
    elif relative_path:
        cleaned = relative_path.strip().lstrip("/")
        if not cleaned or "\\" in cleaned or ".." in cleaned.split("/"):
            raise HTTPException(status_code=400, detail="Invalid world path")
        scope_root = (
            res.source_worlds_dir.resolve()
            if scope == "source"
            else res.patched_worlds_dir.resolve()
        )
        candidate = (scope_root / cleaned).resolve()
        if not candidate.is_relative_to(scope_root) or not candidate.is_file():
            raise HTTPException(status_code=404, detail=f"{scope.title()} world not found")
        source_world_path = candidate
    else:
        source_world_path = _resolve_local_source_world(auto_patch=False)
    world_gen_dir = (
        resolve_world_generated_models_dir(source_world_path, resource=res)
        if source_world_path is not None
        else None
    )
    scene = extract_world_scene(
        source_world_path,
        source_models_dir=res.source_models_dir,
        patched_models_dir=res.patched_models_dir,
        generated_models_dir=res.generated_models_dir,
        world_generated_models_dir=world_gen_dir,
        cache_resolver=ProductionCacheResolver(),
        uri_rule=ProductionFuelUriRule(),
        uncoercer=get_uncoercer(),
        exclude_generated_models=exclude_fleet,
    )
    thumb_rel = relative_path
    if not thumb_rel and source_world_path is not None:
        resolved_src = source_world_path.resolve()
        for base in (res.patched_worlds_dir.resolve(), res.source_worlds_dir.resolve()):
            if resolved_src.is_relative_to(base):
                thumb_rel = resolved_src.relative_to(base).as_posix()
                break
    scene["thumbnail_url"] = (
        find_world_thumbnail_url(thumb_rel, source_models_dir=res.source_models_dir)
        if thumb_rel
        else None
    )
    return scene


_COLLADA_INIT_FROM_RE = re.compile(
    r"(<init_from[^>]*>\s*)([^<]+?)(\s*</init_from>)",
    re.IGNORECASE,
)
_FUEL_URI_MARKER_RE = re.compile(r"/(fuel\.gazebosim\.org/.+)$", re.IGNORECASE)


def _rewrite_collada_asset_uris(
    xml_text: str,
    dae_rel_posix: str,
    *,
    fuel_source_dir: Path | None = None,
) -> str:
    rel_dir = posixpath.dirname(dae_rel_posix)
    cache_resolved = fuel_source_dir.resolve() if fuel_source_dir is not None else None
    uri_rule = ProductionFuelUriRule()
    cache_resolver = ProductionCacheResolver()

    def _replace(match: re.Match[str]) -> str:
        open_tag, raw_uri, close_tag = match.groups()
        trimmed = raw_uri.strip()
        if trimmed.startswith(("model://source_models/", "model://patched_models/", "model://generated_models/")):
            target_rel = trimmed.removeprefix("model://").strip("/")
            rel_from_dae = posixpath.relpath(target_rel, rel_dir)
            return f"{open_tag}{quote(rel_from_dae, safe='/')}{close_tag}"

        if trimmed.lower().startswith("file://"):
            fuel_match = _FUEL_URI_MARKER_RE.search(trimmed)
            if not fuel_match:
                return match.group(0)
            target_rel = f"source_models/fuel/{unquote(fuel_match.group(1))}"
            rel_from_dae = posixpath.relpath(target_rel, rel_dir)
            return f"{open_tag}{quote(rel_from_dae, safe='/')}{close_tag}"

        if trimmed.lower().startswith(("http://", "https://")) and cache_resolved is not None:
            matches = uri_rule.find_all(text=trimmed)
            if matches:
                m = matches[0]
                resolved_dir = cache_resolver.resolve(asset=m.asset)
                if resolved_dir is not None and resolved_dir.resolve().is_relative_to(cache_resolved):
                    target_path = resolved_dir.resolve() / m.subpath.lstrip("/")
                    if target_path.is_file():
                        target_rel = f"source_models/fuel/{target_path.relative_to(cache_resolved).as_posix()}"
                        rel_from_dae = posixpath.relpath(target_rel, rel_dir)
                        return f"{open_tag}{quote(rel_from_dae, safe='/')}{close_tag}"

        return match.group(0)

    return _COLLADA_INIT_FROM_RE.sub(_replace, xml_text)


@app.get("/api/assets/{asset_path:path}", response_model=None)
def get_asset_file(
    asset_path: str,
    geometry_only: bool = False,
    as_glb: bool = False,
) -> Response:
    if not asset_path or asset_path.startswith("/") or "\\" in asset_path:
        raise HTTPException(status_code=400, detail="Invalid asset path")
    res = ResourceSettings.build()
    if asset_path.startswith("source_models/"):
        asset_root = res.source_models_dir.resolve()
        rel_sub = asset_path.removeprefix("source_models/")
        target = (asset_root / rel_sub).resolve()
        dae_rel_posix = f"source_models/{rel_sub}"
    elif asset_path.startswith("patched_models/"):
        asset_root = res.patched_models_dir.resolve()
        rel_sub = asset_path.removeprefix("patched_models/")
        target = (asset_root / rel_sub).resolve()
        dae_rel_posix = f"patched_models/{rel_sub}"
    elif asset_path.startswith("generated_models/"):
        asset_root = res.generated_models_dir.resolve()
        rel_sub = asset_path.removeprefix("generated_models/")
        target = (asset_root / rel_sub).resolve()
        dae_rel_posix = f"generated_models/{rel_sub}"
    else:
        asset_root = res.source_models_of("fuel").resolve()
        target = (asset_root / asset_path).resolve()
        dae_rel_posix = (
            f"source_models/fuel/{target.relative_to(asset_root).as_posix()}"
            if target.is_relative_to(asset_root)
            else asset_path
        )
    if not target.is_relative_to(asset_root) or not target.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    suffix = target.suffix.lower()
    if suffix == ".dae":
        if geometry_only and as_glb:
            glb_bytes = dae_to_geometry_glb(target.read_bytes())
            if glb_bytes is not None:
                return Response(
                    content=glb_bytes,
                    media_type="model/gltf-binary",
                    headers={"Cache-Control": "public, max-age=3600"},
                )
        xml_text = target.read_text(encoding="utf-8", errors="replace")
        if geometry_only:
            rewritten = strip_dae_images(xml_text)
        else:
            rewritten = _rewrite_collada_asset_uris(
                xml_text,
                dae_rel_posix,
                fuel_source_dir=res.source_models_of("fuel"),
            )
        return Response(
            content=rewritten,
            media_type="model/vnd.collada+xml; charset=utf-8",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    if suffix == ".glb":
        if geometry_only:
            stripped = strip_glb_textures(target.read_bytes())
            return Response(
                content=stripped,
                media_type="model/gltf-binary",
                headers={"Cache-Control": "public, max-age=3600"},
            )
        return FileResponse(
            target,
            media_type="model/gltf-binary",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    if suffix == ".gltf":
        return FileResponse(
            target,
            media_type="model/gltf+json",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    return FileResponse(target, headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/worlds/{scope}/{relative_path:path}")
def read_world(scope: WorldScope, relative_path: str) -> dict[str, Any]:
    try:
        return get_world_service().read_world(
            scope=scope, relative_path=relative_path
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/worlds/{scope}/{relative_path:path}")
def delete_world(scope: WorldScope, relative_path: str) -> dict[str, Any]:
    try:
        with acquire_fuel_operation(f"Delete {scope} world: {relative_path}"):
            return get_world_service().delete_world(
                scope=scope, relative_path=relative_path
            )
    except FuelTaskBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/worlds/download")
def download_world(body: WorldDownloadRequest) -> dict[str, Any]:
    try:
        with acquire_fuel_operation(
            f"Download world: {body.world_name or body.world_url or 'world'}"
        ):
            return get_world_service().download_world(
                world_name=body.world_name,
                world_url=body.world_url,
                select=body.select,
            )
    except FuelTaskBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/world/prepare")
def prepare_world() -> dict[str, Any]:
    try:
        with acquire_fuel_operation("Prepare / Patch active world"):
            return get_world_service().prepare_world()
    except FuelTaskBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/worlds/patch")
def patch_world(body: WorldPatchRequest) -> dict[str, Any]:
    try:
        with acquire_fuel_operation(f"Patch world: {body.relative_path}"):
            return get_world_service().patch_world(relative_path=body.relative_path)
    except FuelTaskBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
