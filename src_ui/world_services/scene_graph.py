from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

from s7dcls import StandardUncoercer, StrictUncoercerProtocol

from src_common.conventions.model_name import GENERATED_MODEL_PREFIX
from src_sim.fuel.cache_resolvers.protocol import CacheResolverProtocol
from src_sim.fuel.uri_rules.protocol import FuelUriRuleProtocol
from src_sim.stage_fleet.base_station import find_base_station_pose, parse_sdf_pose
from src_sim.stage_fleet.models import GeoPose

_SDF_TAG_RE = re.compile(r"<sdf\b([^>]*)>", re.IGNORECASE)


def _safe_parse_pose(element: ET.Element | None) -> GeoPose:
    if element is None:
        return GeoPose()
    pose_el = element.find("pose")
    if pose_el is None or not (pose_el.text or "").strip():
        return GeoPose()
    try:
        return parse_sdf_pose(pose_el.text.strip())
    except ValueError:
        return GeoPose()


def _pose_to_mat4(pose: GeoPose) -> list[list[float]]:
    r = math.radians(pose.roll_deg)
    p = math.radians(pose.pitch_deg)
    y = math.radians(pose.yaw_deg)
    cr, sr = math.cos(r), math.sin(r)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr, pose.east_m],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr, pose.north_m],
        [-sp, cp * sr, cp * cr, pose.up_m],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _mat4_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    out = [[0.0] * 4 for _ in range(4)]
    for i in range(4):
        for j in range(4):
            out[i][j] = sum(a[i][k] * b[k][j] for k in range(4))
    return out


def _mat4_to_geopose(m: list[list[float]]) -> GeoPose:
    sy = -m[2][0]
    cy = math.sqrt(max(0.0, 1.0 - sy * sy))
    if cy > 1e-6:
        roll = math.atan2(m[2][1], m[2][2])
        pitch = math.atan2(sy, cy)
        yaw = math.atan2(m[1][0], m[0][0])
    else:
        roll = math.atan2(-m[1][2], m[1][1])
        pitch = math.atan2(sy, cy)
        yaw = 0.0
    return GeoPose(
        east_m=m[0][3],
        north_m=m[1][3],
        up_m=m[2][3],
        roll_deg=math.degrees(roll),
        pitch_deg=math.degrees(pitch),
        yaw_deg=math.degrees(yaw),
    )


def _parse_scale(mesh_el: ET.Element) -> list[float]:
    scale_el = mesh_el.find("scale")
    if scale_el is None or not (scale_el.text or "").strip():
        return [1.0, 1.0, 1.0]
    parts = [float(p) for p in scale_el.text.split()]
    if len(parts) == 3:
        return parts
    if len(parts) == 1:
        return [parts[0], parts[0], parts[0]]
    return [1.0, 1.0, 1.0]


def _parse_sdf_root(sdf_path: Path) -> ET.Element | None:
    text = sdf_path.read_text(encoding="utf-8", errors="replace").lstrip()
    try:
        return ET.fromstring(text)
    except ET.ParseError:
        def _add_ns(match: re.Match[str]) -> str:
            attrs = match.group(1)
            extra = ""
            if "xmlns:gz=" not in attrs:
                extra += ' xmlns:gz="http://gazebosim.org/schema"'
            if "xmlns:ignition=" not in attrs:
                extra += ' xmlns:ignition="http://ignitionrobotics.org/schema"'
            return f"<sdf{attrs}{extra}>"

        patched = _SDF_TAG_RE.sub(_add_ns, text, count=1)
        try:
            return ET.fromstring(patched)
        except ET.ParseError:
            return None


def _resolve_model_sdf(model_dir: Path) -> Path | None:
    config_file = model_dir / "model.config"
    if config_file.is_file():
        try:
            root = ET.parse(config_file).getroot()
            sdf_el = root.find("sdf")
            if sdf_el is not None and (sdf_el.text or "").strip():
                candidate = (model_dir / sdf_el.text.strip()).resolve()
                if candidate.is_file():
                    return candidate
        except ET.ParseError:
            pass
    default_sdf = model_dir / "model.sdf"
    return default_sdf if default_sdf.is_file() else None


def _model_package_roots(
    *,
    source_models_dir: Path,
    patched_models_dir: Path | None,
    generated_models_dir: Path | None,
    world_generated_models_dir: Path | None = None,
) -> list[Path]:
    """Ordered directories containing flat model packages (for resolving `model://<pkg>`)."""
    roots: list[Path] = []
    if world_generated_models_dir is not None and world_generated_models_dir.is_dir():
        roots.append(world_generated_models_dir.resolve())
    elif generated_models_dir is not None and generated_models_dir.is_dir():
        roots.append(generated_models_dir.resolve())
    for base in (patched_models_dir, source_models_dir):
        if base is None or not base.is_dir():
            continue
        for sub in sorted(base.iterdir(), key=lambda p: p.name.lower()):
            if sub.is_dir() and not sub.name.startswith("."):
                roots.append(sub.resolve())
    return roots


def _is_under_allowed_roots(
    cand: Path,
    *,
    source_models_dir: Path,
    patched_models_dir: Path | None,
    generated_models_dir: Path | None,
) -> bool:
    resolved = cand.resolve()
    if resolved.is_relative_to(source_models_dir.resolve()):
        return True
    if patched_models_dir is not None and resolved.is_relative_to(patched_models_dir.resolve()):
        return True
    if generated_models_dir is not None and resolved.is_relative_to(generated_models_dir.resolve()):
        return True
    return False


def _resolve_runtime_uri_target(
    uri_text: str,
    *,
    source_models_dir: Path,
    patched_models_dir: Path | None,
    generated_models_dir: Path | None,
) -> Path | None:
    """Resolve `model://{source_models,patched_models,generated_models}/...` directly."""
    if not uri_text.startswith("model://"):
        return None
    rest = uri_text.removeprefix("model://").strip().strip("/")
    if not rest:
        return None
    bucket_map: dict[str, Path | None] = {
        "source_models": source_models_dir,
        "patched_models": patched_models_dir,
        "generated_models": generated_models_dir,
    }
    if "/" not in rest:
        return None
    bucket, sub = rest.split("/", 1)
    root = bucket_map.get(bucket)
    if root is None:
        return None
    root_res = root.resolve()
    for cand_sub in (sub, unquote(sub)):
        cleaned = cand_sub.strip().strip("/")
        if not cleaned or "\\" in cleaned or ".." in cleaned.split("/"):
            continue
        cand = (root_res / cleaned).resolve()
        if cand.is_relative_to(root_res) and cand.exists():
            return cand
    return None


def _resolve_mesh_file(
    uri_text: str,
    *,
    model_dir: Path | None,
    source_models_dir: Path,
    patched_models_dir: Path | None,
    generated_models_dir: Path | None,
    world_generated_models_dir: Path | None = None,
    cache_resolver: CacheResolverProtocol,
    uri_rule: FuelUriRuleProtocol,
) -> Path | None:
    cleaned = uri_text.strip()
    if not cleaned:
        return None

    if cleaned.startswith("model://"):
        direct = _resolve_runtime_uri_target(
            cleaned,
            source_models_dir=source_models_dir,
            patched_models_dir=patched_models_dir,
            generated_models_dir=generated_models_dir,
        )
        if direct is not None and direct.is_file():
            return direct
        parts = cleaned.removeprefix("model://").split("/", 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            pkg, sub = parts[0], parts[1].lstrip("/")
            for pkg_root in _model_package_roots(
                source_models_dir=source_models_dir,
                patched_models_dir=patched_models_dir,
                generated_models_dir=generated_models_dir,
                world_generated_models_dir=world_generated_models_dir,
            ):
                cand = (pkg_root / pkg / sub).resolve()
                if cand.is_file() and cand.is_relative_to(pkg_root):
                    return cand

    matches = uri_rule.find_all(text=cleaned)
    if matches:
        asset = matches[0].asset
        resolved_dir = cache_resolver.resolve(asset=asset)
        if resolved_dir is not None and "/files/" in cleaned:
            sub = cleaned.split("/files/", 1)[1].lstrip("/")
            cand = (resolved_dir / sub).resolve()
            if cand.is_file() and _is_under_allowed_roots(
                cand,
                source_models_dir=source_models_dir,
                patched_models_dir=patched_models_dir,
                generated_models_dir=generated_models_dir,
            ):
                return cand

    if cleaned.startswith("file://"):
        local = Path(unquote(cleaned.removeprefix("file://"))).resolve()
        if local.is_file() and _is_under_allowed_roots(
            local,
            source_models_dir=source_models_dir,
            patched_models_dir=patched_models_dir,
            generated_models_dir=generated_models_dir,
        ):
            return local

    rel = cleaned
    if rel.startswith("model://"):
        parts = rel.removeprefix("model://").split("/", 1)
        rel = parts[1] if len(parts) == 2 else ""

    if model_dir is not None and rel:
        cand = (model_dir / rel).resolve()
        if cand.is_file() and _is_under_allowed_roots(
            cand,
            source_models_dir=source_models_dir,
            patched_models_dir=patched_models_dir,
            generated_models_dir=generated_models_dir,
        ):
            return cand

    return None


def _file_to_asset_url(
    file_path: Path,
    *,
    source_models_dir: Path,
    patched_models_dir: Path | None = None,
    generated_models_dir: Path | None = None,
) -> str | None:
    resolved = file_path.resolve()
    rel_posix: str | None = None
    if resolved.is_relative_to(source_models_dir.resolve()):
        rel_posix = f"source_models/{resolved.relative_to(source_models_dir.resolve()).as_posix()}"
    elif patched_models_dir is not None and resolved.is_relative_to(patched_models_dir.resolve()):
        rel_posix = f"patched_models/{resolved.relative_to(patched_models_dir.resolve()).as_posix()}"
    elif generated_models_dir is not None and resolved.is_relative_to(generated_models_dir.resolve()):
        rel_posix = f"generated_models/{resolved.relative_to(generated_models_dir.resolve()).as_posix()}"
    if not rel_posix:
        return None
    encoded = "/".join(quote(seg) for seg in rel_posix.split("/"))
    base = f"/api/assets/{encoded}"
    return f"{base}?v=5" if resolved.suffix.lower() == ".dae" else base


def _resolve_model_dir(
    uri_text: str,
    *,
    source_models_dir: Path,
    patched_models_dir: Path | None,
    generated_models_dir: Path | None,
    world_generated_models_dir: Path | None = None,
    cache_resolver: CacheResolverProtocol,
    uri_rule: FuelUriRuleProtocol,
) -> Path | None:
    cleaned = uri_text.strip()
    if not cleaned:
        return None

    if cleaned.startswith("model://"):
        direct = _resolve_runtime_uri_target(
            cleaned,
            source_models_dir=source_models_dir,
            patched_models_dir=patched_models_dir,
            generated_models_dir=generated_models_dir,
        )
        if direct is not None and direct.is_dir():
            return direct

    pkg = (
        cleaned.removeprefix("model://").strip("/")
        if cleaned.startswith("model://")
        else cleaned.strip("/")
    )
    if pkg and "/" not in pkg:
        for pkg_root in _model_package_roots(
            source_models_dir=source_models_dir,
            patched_models_dir=patched_models_dir,
            generated_models_dir=generated_models_dir,
            world_generated_models_dir=world_generated_models_dir,
        ):
            cand = (pkg_root / pkg).resolve()
            if cand.is_dir() and cand.is_relative_to(pkg_root):
                return cand

    matches = uri_rule.find_all(text=cleaned)
    if matches:
        resolved = cache_resolver.resolve(asset=matches[0].asset)
        if resolved is not None:
            return resolved

    if cleaned.startswith("file://"):
        local = Path(unquote(cleaned.removeprefix("file://"))).resolve()
        if local.is_dir() and _is_under_allowed_roots(
            local,
            source_models_dir=source_models_dir,
            patched_models_dir=patched_models_dir,
            generated_models_dir=generated_models_dir,
        ):
            return local

    return None


def _extract_visuals(
    model_root: ET.Element,
    *,
    model_dir: Path | None,
    source_models_dir: Path,
    patched_models_dir: Path | None,
    generated_models_dir: Path | None,
    world_generated_models_dir: Path | None = None,
    cache_resolver: CacheResolverProtocol,
    uri_rule: FuelUriRuleProtocol,
    uncoercer: StrictUncoercerProtocol,
    parent_mat: list[list[float]] | None = None,
    seen_meshes: set[tuple[str, tuple[float, ...], tuple[float, ...]]] | None = None,
    depth: int = 0,
) -> list[dict[str, Any]]:
    if depth > 6:
        return []
    visuals: list[dict[str, Any]] = []
    active_parent = parent_mat or [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    active_seen = seen_meshes if seen_meshes is not None else set()
    identity_pose = uncoercer(value=GeoPose())

    for link_el in model_root.findall("link"):
        link_mat = _mat4_mul(active_parent, _pose_to_mat4(_safe_parse_pose(link_el)))
        for vis_el in link_el.findall("visual"):
            vis_mat = _pose_to_mat4(_safe_parse_pose(vis_el))
            combined_pose = _mat4_to_geopose(_mat4_mul(link_mat, vis_mat))
            geom_el = vis_el.find("geometry")
            if geom_el is None:
                continue

            albedo_url: str | None = None
            albedo_uri = vis_el.findtext("material/pbr/metal/albedo_map")
            if albedo_uri:
                albedo_file = _resolve_mesh_file(
                    albedo_uri,
                    model_dir=model_dir,
                    source_models_dir=source_models_dir,
                    patched_models_dir=patched_models_dir,
                    generated_models_dir=generated_models_dir,
                    world_generated_models_dir=world_generated_models_dir,
                    cache_resolver=cache_resolver,
                    uri_rule=uri_rule,
                )
                if albedo_file is not None:
                    albedo_url = _file_to_asset_url(
                        albedo_file,
                        source_models_dir=source_models_dir,
                        patched_models_dir=patched_models_dir,
                        generated_models_dir=generated_models_dir,
                    )

            diffuse_rgba: list[float] | None = None
            diff_text = (vis_el.findtext("material/diffuse") or "").strip()
            if diff_text:
                try:
                    dvals = [float(v) for v in diff_text.split()]
                    if len(dvals) >= 3:
                        diffuse_rgba = [round(v, 3) for v in (dvals + [1.0])[:4]]
                except ValueError:
                    pass

            geom_data: dict[str, Any] | None = None
            mesh_el = geom_el.find("mesh")
            box_el = geom_el.find("box")
            cyl_el = geom_el.find("cylinder")
            sph_el = geom_el.find("sphere")
            plane_el = geom_el.find("plane")
            poly_el = geom_el.find("polyline")
            hmap_el = geom_el.find("heightmap")

            if mesh_el is not None:
                uri_el = mesh_el.find("uri")
                if uri_el is not None and (uri_el.text or "").strip():
                    mesh_file = _resolve_mesh_file(
                        uri_el.text,
                        model_dir=model_dir,
                        source_models_dir=source_models_dir,
                        patched_models_dir=patched_models_dir,
                        generated_models_dir=generated_models_dir,
                        world_generated_models_dir=world_generated_models_dir,
                        cache_resolver=cache_resolver,
                        uri_rule=uri_rule,
                    )
                    if mesh_file is not None:
                        asset_url = _file_to_asset_url(
                            mesh_file,
                            source_models_dir=source_models_dir,
                            patched_models_dir=patched_models_dir,
                            generated_models_dir=generated_models_dir,
                        )
                        if asset_url is None:
                            continue
                        scale = _parse_scale(mesh_el)
                        pose_key = (
                            round(combined_pose.east_m, 4),
                            round(combined_pose.north_m, 4),
                            round(combined_pose.up_m, 4),
                            round(combined_pose.roll_deg, 2),
                            round(combined_pose.pitch_deg, 2),
                            round(combined_pose.yaw_deg, 2),
                        )
                        scale_key = tuple(round(v, 4) for v in scale)
                        dedup_key = (asset_url, pose_key, scale_key)
                        if dedup_key in active_seen:
                            continue
                        active_seen.add(dedup_key)
                        geom_data = {
                            "type": "mesh",
                            "asset_url": asset_url,
                            "ext": mesh_file.suffix.lower(),
                            "scale": scale,
                        }
            elif box_el is not None:
                size_el = box_el.find("size")
                if size_el is not None and (size_el.text or "").strip():
                    geom_data = {
                        "type": "box",
                        "size": [float(v) for v in size_el.text.split()[:3]],
                    }
            elif cyl_el is not None:
                r = cyl_el.findtext("radius")
                length = cyl_el.findtext("length")
                if r and length:
                    geom_data = {
                        "type": "cylinder",
                        "radius": float(r),
                        "length": float(length),
                    }
            elif sph_el is not None:
                r = sph_el.findtext("radius")
                if r:
                    geom_data = {"type": "sphere", "radius": float(r)}
            elif plane_el is not None:
                size_text = (plane_el.findtext("size") or "100 100").strip()
                parts = [float(v) for v in size_text.split()[:2]]
                sx = parts[0] if len(parts) >= 1 else 100.0
                sy = parts[1] if len(parts) >= 2 else sx
                combined_pose = GeoPose(
                    east_m=combined_pose.east_m,
                    north_m=combined_pose.north_m,
                    up_m=combined_pose.up_m - 0.001,
                    roll_deg=combined_pose.roll_deg,
                    pitch_deg=combined_pose.pitch_deg,
                    yaw_deg=combined_pose.yaw_deg,
                )
                geom_data = {"type": "box", "size": [sx, sy, 0.002]}
            elif poly_el is not None:
                pts: list[tuple[float, float]] = []
                for pt_el in poly_el.findall("point"):
                    if pt_el.text:
                        coords = [float(v) for v in pt_el.text.split()[:2]]
                        if len(coords) == 2:
                            pts.append((coords[0], coords[1]))
                if pts:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    h = float((poly_el.findtext("height") or "1").strip())
                    cx = (min(xs) + max(xs)) * 0.5
                    cy = (min(ys) + max(ys)) * 0.5
                    combined_pose = GeoPose(
                        east_m=combined_pose.east_m + cx,
                        north_m=combined_pose.north_m + cy,
                        up_m=combined_pose.up_m + h * 0.5,
                        roll_deg=combined_pose.roll_deg,
                        pitch_deg=combined_pose.pitch_deg,
                        yaw_deg=combined_pose.yaw_deg,
                    )
                    geom_data = {
                        "type": "box",
                        "size": [
                            max(0.2, max(xs) - min(xs)),
                            max(0.2, max(ys) - min(ys)),
                            max(0.1, h),
                        ],
                    }
            elif hmap_el is not None:
                size_text = (hmap_el.findtext("size") or "100 100 10").strip()
                parts = [float(v) for v in size_text.split()[:3]]
                sx = parts[0] if len(parts) >= 1 else 100.0
                sy = parts[1] if len(parts) >= 2 else sx
                sz = parts[2] if len(parts) >= 3 else 10.0
                pos_text = (hmap_el.findtext("pos") or "").strip()
                px, py, pz = 0.0, 0.0, 0.0
                if pos_text:
                    pvals = [float(v) for v in pos_text.split()[:3]]
                    px = pvals[0] if len(pvals) >= 1 else 0.0
                    py = pvals[1] if len(pvals) >= 2 else 0.0
                    pz = pvals[2] if len(pvals) >= 3 else 0.0
                if not albedo_url:
                    diff_uri = hmap_el.findtext("texture/diffuse")
                    if diff_uri:
                        diff_file = _resolve_mesh_file(
                            diff_uri,
                            model_dir=model_dir,
                            source_models_dir=source_models_dir,
                            patched_models_dir=patched_models_dir,
                            generated_models_dir=generated_models_dir,
                            cache_resolver=cache_resolver,
                            uri_rule=uri_rule,
                        )
                        if diff_file is not None:
                            albedo_url = _file_to_asset_url(
                                diff_file,
                                source_models_dir=source_models_dir,
                                patched_models_dir=patched_models_dir,
                                generated_models_dir=generated_models_dir,
                            )
                thickness = max(0.2, min(2.0, sz * 0.05))
                combined_pose = GeoPose(
                    east_m=combined_pose.east_m + px,
                    north_m=combined_pose.north_m + py,
                    up_m=combined_pose.up_m + pz - thickness * 0.5,
                    roll_deg=combined_pose.roll_deg,
                    pitch_deg=combined_pose.pitch_deg,
                    yaw_deg=combined_pose.yaw_deg,
                )
                geom_data = {"type": "box", "size": [sx, sy, thickness]}

            if geom_data is not None:
                visuals.append(
                    {
                        "link_pose": uncoercer(value=combined_pose),
                        "visual_pose": identity_pose,
                        "geometry": geom_data,
                        "albedo_url": albedo_url,
                        "diffuse_rgba": diffuse_rgba,
                    }
                )

    for nested_model in model_root.findall("model"):
        nested_mat = _mat4_mul(active_parent, _pose_to_mat4(_safe_parse_pose(nested_model)))
        visuals.extend(
            _extract_visuals(
                nested_model,
                model_dir=model_dir,
                source_models_dir=source_models_dir,
                patched_models_dir=patched_models_dir,
                generated_models_dir=generated_models_dir,
                world_generated_models_dir=world_generated_models_dir,
                cache_resolver=cache_resolver,
                uri_rule=uri_rule,
                uncoercer=uncoercer,
                parent_mat=nested_mat,
                seen_meshes=active_seen,
                depth=depth + 1,
            )
        )

    for inc_el in model_root.findall("include"):
        uri_text = (inc_el.findtext("uri") or "").strip()
        if not uri_text:
            continue
        inc_dir = _resolve_model_dir(
            uri_text,
            source_models_dir=source_models_dir,
            patched_models_dir=patched_models_dir,
            generated_models_dir=generated_models_dir,
            world_generated_models_dir=world_generated_models_dir,
            cache_resolver=cache_resolver,
            uri_rule=uri_rule,
        )
        if inc_dir is None:
            continue
        inc_sdf = _resolve_model_sdf(inc_dir)
        if inc_sdf is None:
            continue
        inc_root = _parse_sdf_root(inc_sdf)
        if inc_root is None:
            continue
        inc_model = inc_root if inc_root.tag == "model" else inc_root.find("model")
        if inc_model is None:
            continue
        inc_mat = _mat4_mul(active_parent, _pose_to_mat4(_safe_parse_pose(inc_el)))
        inc_mat = _mat4_mul(inc_mat, _pose_to_mat4(_safe_parse_pose(inc_model)))
        visuals.extend(
            _extract_visuals(
                inc_model,
                model_dir=inc_dir,
                source_models_dir=source_models_dir,
                patched_models_dir=patched_models_dir,
                generated_models_dir=generated_models_dir,
                world_generated_models_dir=world_generated_models_dir,
                cache_resolver=cache_resolver,
                uri_rule=uri_rule,
                uncoercer=uncoercer,
                parent_mat=inc_mat,
                seen_meshes=active_seen,
                depth=depth + 1,
            )
        )

    return visuals


def extract_model_visuals(
    model_path: Path,
    *,
    source_models_dir: Path,
    patched_models_dir: Path | None = None,
    generated_models_dir: Path | None = None,
    world_generated_models_dir: Path | None = None,
    cache_resolver: CacheResolverProtocol,
    uri_rule: FuelUriRuleProtocol,
    uncoercer: StrictUncoercerProtocol | None = None,
) -> list[dict[str, Any]]:
    """Extract 3D visuals from any model directory or `.sdf` file (Fuel, PX4, generated, custom)."""
    active_uncoercer = uncoercer or StandardUncoercer.Args().build()
    if model_path.is_file():
        sdf_path: Path | None = model_path
        model_dir = model_path.parent
    else:
        model_dir = model_path
        sdf_path = _resolve_model_sdf(model_dir)
    if sdf_path is None or not sdf_path.is_file():
        return []
    m_root = _parse_sdf_root(sdf_path)
    if m_root is None:
        return []
    target_el = m_root.find("model") if m_root.tag == "sdf" and m_root.find("model") is not None else m_root
    raw = _extract_visuals(
        target_el,
        model_dir=model_dir,
        source_models_dir=source_models_dir,
        patched_models_dir=patched_models_dir,
        generated_models_dir=generated_models_dir,
        world_generated_models_dir=world_generated_models_dir,
        cache_resolver=cache_resolver,
        uri_rule=uri_rule,
        uncoercer=active_uncoercer,
    )
    has_mesh = any(v["geometry"].get("type") == "mesh" for v in raw)
    if model_dir.name.startswith("x500") and has_mesh:
        return [v for v in raw if v["geometry"].get("type") == "mesh"]
    return raw


def extract_world_scene(
    sdf_path: Path | None,
    *,
    source_models_dir: Path,
    patched_models_dir: Path | None = None,
    generated_models_dir: Path | None = None,
    world_generated_models_dir: Path | None = None,
    cache_resolver: CacheResolverProtocol,
    uri_rule: FuelUriRuleProtocol,
    uncoercer: StrictUncoercerProtocol | None = None,
    exclude_generated_models: bool = False,
) -> dict[str, Any]:
    active_uncoercer = uncoercer or StandardUncoercer.Args().build()
    if sdf_path is None or not sdf_path.is_file():
        return {
            "source_world": None,
            "base_station": None,
            "models": [],
        }

    root = _parse_sdf_root(sdf_path)
    if root is None:
        return {
            "source_world": str(sdf_path),
            "base_station": None,
            "models": [],
        }
    world_el = root if root.tag == "world" else root.find("world")
    if world_el is None:
        return {
            "source_world": str(sdf_path),
            "base_station": None,
            "models": [],
        }

    base_station = find_base_station_pose(world_el)
    models: list[dict[str, Any]] = []

    generated_root_resolved = (
        generated_models_dir.resolve() if generated_models_dir is not None else None
    )
    generated_uri_prefix = f"model://{GENERATED_MODEL_PREFIX}"

    for inc_el in world_el.findall("include"):
        name = (inc_el.findtext("name") or "").strip() or "unnamed"
        pose = _safe_parse_pose(inc_el)
        uri_text = (inc_el.findtext("uri") or "").strip()
        if exclude_generated_models and (
            uri_text.startswith("model://generated_models/")
            or uri_text.startswith(generated_uri_prefix)
        ):
            continue
        visuals: list[dict[str, Any]] = []

        if uri_text:
            model_dir = _resolve_model_dir(
                uri_text,
                source_models_dir=source_models_dir,
                patched_models_dir=patched_models_dir,
                generated_models_dir=generated_models_dir,
                world_generated_models_dir=world_generated_models_dir,
                cache_resolver=cache_resolver,
                uri_rule=uri_rule,
            )
            if (
                exclude_generated_models
                and model_dir is not None
                and generated_root_resolved is not None
                and model_dir.resolve().is_relative_to(generated_root_resolved)
            ):
                continue
            if model_dir is not None:
                model_sdf = _resolve_model_sdf(model_dir)
                if model_sdf is not None:
                    m_root = _parse_sdf_root(model_sdf)
                    if m_root is not None:
                        m_el = m_root if m_root.tag == "model" else m_root.find("model")
                        if m_el is not None:
                            visuals = _extract_visuals(
                                m_el,
                                model_dir=model_dir,
                                source_models_dir=source_models_dir,
                                patched_models_dir=patched_models_dir,
                                generated_models_dir=generated_models_dir,
                                world_generated_models_dir=world_generated_models_dir,
                                cache_resolver=cache_resolver,
                                uri_rule=uri_rule,
                                uncoercer=active_uncoercer,
                                parent_mat=_pose_to_mat4(_safe_parse_pose(m_el)),
                            )

        models.append(
            {
                "name": name,
                "is_base_station": name == "base_station",
                "pose": active_uncoercer(value=pose),
                "visuals": visuals,
            }
        )

    for model_el in world_el.findall("model"):
        name = model_el.attrib.get("name", "unnamed")
        pose = _safe_parse_pose(model_el)
        visuals = _extract_visuals(
            model_el,
            model_dir=None,
            source_models_dir=source_models_dir,
            patched_models_dir=patched_models_dir,
            generated_models_dir=generated_models_dir,
            cache_resolver=cache_resolver,
            uri_rule=uri_rule,
            uncoercer=active_uncoercer,
        )
        models.append(
            {
                "name": name,
                "is_base_station": name == "base_station",
                "pose": active_uncoercer(value=pose),
                "visuals": visuals,
            }
        )

    return {
        "source_world": str(sdf_path),
        "base_station": active_uncoercer(value=base_station),
        "models": models,
    }


__all__ = [
    "extract_model_visuals",
    "extract_world_scene",
]
