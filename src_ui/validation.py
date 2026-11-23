from __future__ import annotations

import math
import re
from typing import Any

_NAMESPACE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _is_finite_number(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(float(val))


def _check_pose_dict(pose: Any, label: str, keys: tuple[str, ...], errors: list[str]) -> None:
    if not isinstance(pose, dict):
        errors.append(f"{label}: expected object")
        return
    for key in keys:
        if key in pose and pose[key] is not None and not _is_finite_number(pose[key]):
            errors.append(f"{label}.{key}: must be a finite number")


def validate_asset_ref(ref: Any, *, label: str, require_sdf: bool = True) -> list[str]:
    if not isinstance(ref, dict):
        return [f"{label}: expected catalog or path asset reference object"]
    kind = ref.get("kind")
    if kind == "catalog":
        rel = str(ref.get("relative_path") or "").strip()
        if not rel:
            return [f"{label}: catalog relative_path is required"]
        if "\\" in rel or ".." in rel.split("/") or rel.startswith("/"):
            return [f"{label}: invalid catalog relative_path '{rel}'"]
        if require_sdf and not rel.lower().endswith(".sdf"):
            return [f"{label}: catalog relative_path must end with .sdf ('{rel}')"]
        return []
    if kind == "path":
        raw = str(ref.get("path") or "").strip()
        if not raw:
            return [f"{label}: path is required"]
        if "\\" in raw:
            return [f"{label}: invalid path '{raw}'"]
        if require_sdf and not raw.lower().endswith(".sdf"):
            return [f"{label}: path must end with .sdf ('{raw}')"]
        return []
    return [f"{label}: kind must be 'catalog' or 'path' (got {kind!r})"]


def validate_vehicles_list(vehicles: Any, *, prefix_label: str = "") -> list[str]:
    if not isinstance(vehicles, list):
        return [f"{prefix_label}vehicles must be a list"]

    errors: list[str] = []
    seen_ns: dict[str, int] = {}

    for idx, item in enumerate(vehicles, start=1):
        prefix = f"{prefix_label}Vehicle #{idx}"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: expected vehicle object")
            continue

        airframe = item.get("airframe")
        if airframe is None:
            errors.append(f"{prefix}: airframe is required")
        else:
            errors.extend(validate_asset_ref(airframe, label=f"{prefix}.airframe"))

        ns = str(item.get("namespace") or "").strip()
        if not ns:
            errors.append(f"{prefix}: namespace is required")
        elif not _NAMESPACE_RE.match(ns):
            errors.append(
                f"{prefix}: namespace '{ns}' must start with a letter/_ and contain only letters, digits, or _"
            )
        elif ns in seen_ns:
            errors.append(f"{prefix}: duplicate namespace '{ns}' (already used by Vehicle #{seen_ns[ns]})")
        else:
            seen_ns[ns] = idx

        for group_key in ("attachments", "devices"):
            entries = item.get(group_key)
            if entries is None:
                continue
            if not isinstance(entries, list):
                errors.append(f"{prefix}.{group_key}: must be a list")
                continue
            for sub_idx, sub in enumerate(entries, start=1):
                if not isinstance(sub, dict):
                    errors.append(f"{prefix}.{group_key}[{sub_idx}]: expected object")
                    continue
                pose_offset = sub.get("pose_offset")
                if pose_offset is not None:
                    _check_pose_dict(
                        pose_offset,
                        f"{prefix}.{group_key}[{sub_idx}].pose_offset",
                        ("forward_m", "left_m", "up_m", "roll_rad", "pitch_rad", "yaw_rad"),
                        errors,
                    )

    return errors


def _validate_world_fleet_entry(world_key: str, cfg: Any, errors: list[str]) -> None:
    label = f"[{world_key}] "
    if not isinstance(cfg, dict):
        errors.append(f"{label}expected fleet config object")
        return

    if "vehicles" in cfg and cfg["vehicles"] is not None:
        errors.extend(validate_vehicles_list(cfg["vehicles"], prefix_label=label))

    fm = cfg.get("formation")
    if isinstance(fm, dict):
        for key in ("spacing_m", "radius_m", "min_separation_m"):
            if key in fm and fm[key] is not None:
                val = fm[key]
                if not _is_finite_number(val):
                    errors.append(f"{label}Formation.{key}: must be a finite number")
                elif float(val) <= 0:
                    errors.append(f"{label}Formation.{key}: must be > 0")

    center = cfg.get("center")
    if isinstance(center, dict):
        if isinstance(center.get("pose"), dict):
            _check_pose_dict(
                center["pose"],
                f"{label}FleetCenter.pose",
                ("east_m", "north_m", "up_m", "roll_deg", "pitch_deg", "yaw_deg"),
                errors,
            )
        for non_neg in ("base_station_half_m", "gap_m"):
            if non_neg in center and center[non_neg] is not None:
                if not _is_finite_number(center[non_neg]) or float(center[non_neg]) < 0:
                    errors.append(f"{label}FleetCenter.{non_neg}: must be >= 0")

    pose_overrides = cfg.get("pose_overrides")
    if isinstance(pose_overrides, dict):
        for ns, pose in pose_overrides.items():
            _check_pose_dict(
                pose,
                f"{label}PoseOverride[{ns}]",
                ("east_m", "north_m", "up_m", "roll_deg", "pitch_deg", "yaw_deg"),
                errors,
            )


def validate_settings_updates(updates: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if "__SIM__ACTIVE_WORLD" in updates and updates["__SIM__ACTIVE_WORLD"] is not None:
        errors.extend(
            validate_asset_ref(updates["__SIM__ACTIVE_WORLD"], label="__SIM__ACTIVE_WORLD")
        )

    if "__SIM__FLEET__WORLDS" in updates and updates["__SIM__FLEET__WORLDS"] is not None:
        worlds_map = updates["__SIM__FLEET__WORLDS"]
        if not isinstance(worlds_map, dict):
            errors.append("__SIM__FLEET__WORLDS must be an object mapping world key -> fleet config")
        else:
            for world_key, cfg in worlds_map.items():
                if not isinstance(world_key, str) or not world_key.strip():
                    errors.append("__SIM__FLEET__WORLDS keys must be non-empty world keys")
                    continue
                _validate_world_fleet_entry(world_key, cfg, errors)

    return errors


__all__ = ["validate_asset_ref", "validate_settings_updates", "validate_vehicles_list"]
