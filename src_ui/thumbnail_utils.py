from __future__ import annotations

import array
import json
import math
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import quote

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_GLB_MAGIC = b"glTF"
_CHUNK_JSON = 0x4E4F534A
_CHUNK_BIN = 0x004E4942

_STRIPPED_MAT_KEYS = (
    "normalTexture",
    "occlusionTexture",
    "emissiveTexture",
    "extensions",
)
_STRIPPED_PBR_KEYS = (
    "baseColorTexture",
    "metallicRoughnessTexture",
)
_STRIPPED_EXT_PREFIXES = (
    "KHR_texture_",
    "KHR_materials_",
    "EXT_texture_",
)
_DAE_LIB_IMAGES_RE = re.compile(
    r"<library_images\b[^>]*>.*?</library_images>",
    re.IGNORECASE | re.DOTALL,
)


def find_asset_thumbnail(asset_dir: Path) -> Path | None:
    thumbs_dir = asset_dir / "thumbnails"
    if not thumbs_dir.is_dir():
        return None
    candidates = [
        p
        for p in thumbs_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTS and p.stat().st_size > 0
    ]
    if not candidates:
        return None

    def _sort_key(p: Path) -> tuple[int, str]:
        stem = p.stem.lower()
        if stem in {"0", "1"}:
            return (0, stem)
        if stem.isdigit():
            return (1, f"{int(stem):06d}")
        return (2, p.name.lower())

    candidates.sort(key=_sort_key)
    return candidates[0]


def _path_to_asset_url(
    file_path: Path,
    *,
    source_models_dir: Path,
    patched_models_dir: Path | None = None,
) -> str | None:
    resolved = file_path.resolve()
    src_root = source_models_dir.resolve()
    rel_posix: str | None = None
    if resolved.is_relative_to(src_root):
        rel_posix = f"source_models/{resolved.relative_to(src_root).as_posix()}"
    elif patched_models_dir is not None and resolved.is_relative_to(
        patched_models_dir.resolve()
    ):
        rel_posix = (
            f"patched_models/{resolved.relative_to(patched_models_dir.resolve()).as_posix()}"
        )
    if not rel_posix:
        return None
    encoded = "/".join(quote(seg) for seg in rel_posix.split("/"))
    return f"/api/assets/{encoded}"


def find_model_thumbnail_url(
    model_dir: Path,
    *,
    source_models_dir: Path,
    patched_models_dir: Path | None = None,
    relative_path: str | None = None,
) -> str | None:
    thumb = find_asset_thumbnail(model_dir)
    if thumb is not None:
        return _path_to_asset_url(
            thumb,
            source_models_dir=source_models_dir,
            patched_models_dir=patched_models_dir,
        )
    if relative_path:
        fallback_dir = (source_models_dir / relative_path.strip().lstrip("/")).resolve()
        if fallback_dir.is_relative_to(source_models_dir.resolve()) and fallback_dir.is_dir():
            thumb = find_asset_thumbnail(fallback_dir)
            if thumb is not None:
                return _path_to_asset_url(
                    thumb,
                    source_models_dir=source_models_dir,
                    patched_models_dir=patched_models_dir,
                )
    return None


def find_world_thumbnail_url(
    relative_path: str,
    *,
    source_models_dir: Path,
) -> str | None:
    cleaned = relative_path.strip().lstrip("/")
    if cleaned.startswith("fuel/"):
        cleaned = cleaned.removeprefix("fuel/")
    if not cleaned.lower().endswith(".sdf"):
        return None
    without_ext = cleaned[:-4]
    if "/" not in without_ext:
        return None
    owner, world_name = without_ext.split("/", 1)
    owner_lc = owner.strip().lower()
    world_lc = world_name.strip().lower()
    fuel_root = (source_models_dir / "fuel").resolve()
    if not owner_lc or not world_lc or not fuel_root.is_dir():
        return None

    for server_dir in sorted(fuel_root.iterdir(), key=lambda p: p.name.lower()):
        if not server_dir.is_dir() or server_dir.name.startswith("."):
            continue
        worlds_dir = server_dir / owner_lc / "worlds" / world_lc
        if not worlds_dir.is_dir():
            continue
        versions = [d for d in worlds_dir.iterdir() if d.is_dir()]
        versions.sort(
            key=lambda d: (0, -int(d.name)) if d.name.isdigit() else (1, d.name.lower())
        )
        for ver_dir in versions:
            thumb = find_asset_thumbnail(ver_dir)
            if thumb is not None:
                return _path_to_asset_url(thumb, source_models_dir=source_models_dir)
    return None


def strip_dae_images(xml_text: str) -> str:
    return _DAE_LIB_IMAGES_RE.sub("", xml_text)


def _mat4_identity() -> list[float]:
    return [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]


def _mat4_mul_rm(a: list[float], b: list[float]) -> list[float]:
    """Multiply two row-major 4x4 matrices."""
    out = [0.0] * 16
    for r in range(4):
        r4 = r * 4
        a0, a1, a2, a3 = a[r4], a[r4 + 1], a[r4 + 2], a[r4 + 3]
        for c in range(4):
            out[r4 + c] = a0 * b[c] + a1 * b[4 + c] + a2 * b[8 + c] + a3 * b[12 + c]
    return out


def _mat4_to_col_major(m: list[float]) -> list[float]:
    return [
        m[0], m[4], m[8], m[12],
        m[1], m[5], m[9], m[13],
        m[2], m[6], m[10], m[14],
        m[3], m[7], m[11], m[15],
    ]


def _mat4_rotate_axis(x: float, y: float, z: float, angle_deg: float) -> list[float]:
    length = math.sqrt(x * x + y * y + z * z)
    if length < 1e-9:
        return _mat4_identity()
    x, y, z = x / length, y / length, z / length
    rad = math.radians(angle_deg)
    c, s = math.cos(rad), math.sin(rad)
    t = 1.0 - c
    return [
        t * x * x + c, t * x * y - s * z, t * x * z + s * y, 0.0,
        t * x * y + s * z, t * y * y + c, t * y * z - s * x, 0.0,
        t * x * z - s * y, t * y * z + s * x, t * z * z + c, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]


def _dae_node_local_matrix(node_el: ET.Element) -> list[float]:
    mat = _mat4_identity()
    for child in node_el:
        tag = child.tag.rsplit("}", 1)[-1]
        txt = (child.text or "").strip()
        if not txt:
            continue
        if tag == "matrix":
            vals = [float(v) for v in txt.split()]
            if len(vals) == 16:
                mat = _mat4_mul_rm(mat, vals)
        elif tag == "translate":
            vals = [float(v) for v in txt.split()]
            if len(vals) == 3:
                t = _mat4_identity()
                t[3], t[7], t[11] = vals[0], vals[1], vals[2]
                mat = _mat4_mul_rm(mat, t)
        elif tag == "rotate":
            vals = [float(v) for v in txt.split()]
            if len(vals) == 4:
                mat = _mat4_mul_rm(mat, _mat4_rotate_axis(vals[0], vals[1], vals[2], vals[3]))
        elif tag == "scale":
            vals = [float(v) for v in txt.split()]
            if len(vals) == 3:
                s = _mat4_identity()
                s[0], s[5], s[10] = vals[0], vals[1], vals[2]
                mat = _mat4_mul_rm(mat, s)
    return mat


def _dae_extract_material_colors(
    root: ET.Element, pre: str, ns: dict[str, str]
) -> dict[str, list[float]]:
    effect_colors: dict[str, list[float]] = {}
    for eff in root.findall(f".//{pre}library_effects/{pre}effect", ns):
        eid = eff.attrib.get("id")
        if not eid:
            continue
        color_el = eff.find(f".//{pre}diffuse/{pre}color", ns)
        if color_el is not None and color_el.text:
            try:
                vals = [float(v) for v in color_el.text.split()]
                if len(vals) >= 3:
                    rgba = [max(0.0, min(1.0, v)) for v in (vals + [1.0])[:4]]
                    effect_colors[eid] = rgba
            except ValueError:
                pass

    mat_colors: dict[str, list[float]] = {}
    for mat in root.findall(f".//{pre}library_materials/{pre}material", ns):
        mid = mat.attrib.get("id")
        if not mid:
            continue
        ieff = mat.find(f"{pre}instance_effect", ns)
        if ieff is not None:
            url = (ieff.attrib.get("url") or "").lstrip("#")
            if url in effect_colors:
                mat_colors[mid] = effect_colors[url]
    return mat_colors


def dae_to_geometry_glb(raw: bytes) -> bytes | None:
    """Convert a Collada (.dae) XML payload into a compact, lossless indexed GLB 2.0.

    Only POSITION buffers, triangle indices, scene-graph node transforms, unit/up-axis
    normalization (to Gazebo Z-up meters), and flat diffuse colors are emitted.
    Returns None if the DAE contains no convertible triangle/polylist geometry.
    """
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None

    ns = {"c": root.tag.split("}")[0].lstrip("{")} if "}" in root.tag else {}
    pre = "c:" if ns else ""

    unit_el = root.find(f"{pre}asset/{pre}unit", ns)
    unit_scale = 1.0
    if unit_el is not None:
        try:
            unit_scale = float(unit_el.attrib.get("meter", "1"))
            if not math.isfinite(unit_scale) or unit_scale <= 0:
                unit_scale = 1.0
        except ValueError:
            unit_scale = 1.0

    mat_colors_by_id = _dae_extract_material_colors(root, pre, ns)

    # First pass: scan geometries to find only POSITION sources actually needed.
    pos_sources_needed: set[str] = set()
    geom_prim_specs: dict[str, list[tuple[str, int, int, str, str | None, str | None]]] = {}

    for geom in root.findall(f".//{pre}library_geometries/{pre}geometry", ns):
        gid = geom.attrib.get("id")
        if not gid:
            continue
        mesh = geom.find(f"{pre}mesh", ns)
        if mesh is None:
            continue
        verts_el = mesh.find(f"{pre}vertices", ns)
        verts_id = verts_el.attrib.get("id") if verts_el is not None else None
        verts_pos_src: str | None = None
        if verts_el is not None:
            for inp in verts_el.findall(f"{pre}input", ns):
                if inp.attrib.get("semantic") == "POSITION":
                    verts_pos_src = (inp.attrib.get("source") or "").lstrip("#")

        prims: list[tuple[str, int, int, str, str | None, str | None]] = []
        for child in mesh:
            tag = child.tag.rsplit("}", 1)[-1]
            if tag not in {"triangles", "polylist"}:
                continue
            inputs = child.findall(f"{pre}input", ns)
            if not inputs:
                continue
            max_off = max(int(i.attrib.get("offset", "0")) for i in inputs)
            step = max_off + 1
            p_off: int | None = None
            pos_src: str | None = None
            for inp in inputs:
                sem = inp.attrib.get("semantic")
                off = int(inp.attrib.get("offset", "0"))
                src = (inp.attrib.get("source") or "").lstrip("#")
                if sem == "VERTEX" and src == verts_id:
                    p_off = off
                    pos_src = verts_pos_src
                elif sem == "POSITION":
                    p_off = off
                    pos_src = src
            p_el = child.find(f"{pre}p", ns)
            if p_off is None or not pos_src or p_el is None or not p_el.text:
                continue
            vcount_text: str | None = None
            if tag == "polylist":
                vc_el = child.find(f"{pre}vcount", ns)
                if vc_el is None or not vc_el.text:
                    continue
                vcount_text = vc_el.text
            mat_sym = child.attrib.get("material")
            pos_sources_needed.add(pos_src)
            prims.append((pos_src, p_off, step, p_el.text, vcount_text, mat_sym))
        if prims:
            geom_prim_specs[gid] = prims

    if not geom_prim_specs:
        return None

    # Parse ONLY needed POSITION float_arrays (skips NORMAL & TEXCOORD arrays completely).
    pos_arrays: dict[str, array.array] = {}
    for src in root.findall(f".//{pre}library_geometries//{pre}source", ns):
        sid = src.attrib.get("id")
        if sid in pos_sources_needed:
            fa = src.find(f"{pre}float_array", ns)
            if fa is not None and fa.text:
                try:
                    pos_arrays[sid] = array.array("f", map(float, fa.text.split()))
                except ValueError:
                    continue

    # Build GLB binary buffer, bufferViews, accessors, and materials.
    bin_parts: list[bytes] = []
    bin_offset = 0
    buffer_views: list[dict[str, Any]] = []
    accessors: list[dict[str, Any]] = []

    def _append_bv(data: bytes, target: int) -> int:
        nonlocal bin_offset
        pad = (-bin_offset) % 4
        if pad:
            bin_parts.append(b"\x00" * pad)
            bin_offset += pad
        bv_idx = len(buffer_views)
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": bin_offset,
                "byteLength": len(data),
                "target": target,
            }
        )
        bin_parts.append(data)
        bin_offset += len(data)
        return bv_idx

    pos_accessor_by_src: dict[str, tuple[int, int]] = {}
    for sid, arr in pos_arrays.items():
        n_verts = len(arr) // 3
        if n_verts <= 0:
            continue
        if len(arr) != n_verts * 3:
            arr = arr[: n_verts * 3]
        xs = arr[0::3]
        ys = arr[1::3]
        zs = arr[2::3]
        bv_idx = _append_bv(arr.tobytes(), 34962)  # ARRAY_BUFFER
        acc_idx = len(accessors)
        accessors.append(
            {
                "bufferView": bv_idx,
                "componentType": 5126,  # FLOAT
                "count": n_verts,
                "type": "VEC3",
                "min": [min(xs), min(ys), min(zs)],
                "max": [max(xs), max(ys), max(zs)],
            }
        )
        pos_accessor_by_src[sid] = (acc_idx, n_verts)

    if not pos_accessor_by_src:
        return None

    materials: list[dict[str, Any]] = []
    mat_idx_by_rgba: dict[tuple[float, float, float, float], int] = {}

    def _get_material_idx(rgba: list[float] | None) -> int | None:
        if not rgba:
            return None
        key = (round(rgba[0], 3), round(rgba[1], 3), round(rgba[2], 3), round(rgba[3], 3))
        existing = mat_idx_by_rgba.get(key)
        if existing is not None:
            return existing
        idx = len(materials)
        materials.append(
            {
                "pbrMetallicRoughness": {
                    "baseColorFactor": [key[0], key[1], key[2], key[3]],
                    "metallicFactor": 0.1,
                    "roughnessFactor": 0.75,
                }
            }
        )
        mat_idx_by_rgba[key] = idx
        return idx

    # Pre-build raw primitive index accessors per Collada geometry id.
    geom_prims_built: dict[str, list[tuple[int, int, str | None]]] = {}
    for gid, prims in geom_prim_specs.items():
        built_list: list[tuple[int, int, str | None]] = []
        for pos_src, p_off, step, p_txt, vcount_txt, mat_sym in prims:
            pos_info = pos_accessor_by_src.get(pos_src)
            if pos_info is None:
                continue
            pos_acc_idx, n_verts = pos_info
            try:
                p_ints = list(map(int, p_txt.split()))
            except ValueError:
                continue
            if vcount_txt is None:
                idx_list = p_ints[p_off::step]
                n_tri_verts = (len(idx_list) // 3) * 3
                if n_tri_verts <= 0:
                    continue
                if len(idx_list) != n_tri_verts:
                    idx_list = idx_list[:n_tri_verts]
            else:
                try:
                    vcounts = list(map(int, vcount_txt.split()))
                except ValueError:
                    continue
                idx_list = []
                cursor = 0
                total_p = len(p_ints)
                for vc in vcounts:
                    if vc < 3 or cursor + vc * step > total_p:
                        cursor += max(0, vc) * step
                        continue
                    v0 = p_ints[cursor + p_off]
                    for k in range(1, vc - 1):
                        idx_list.append(v0)
                        idx_list.append(p_ints[cursor + k * step + p_off])
                        idx_list.append(p_ints[cursor + (k + 1) * step + p_off])
                    cursor += vc * step
                if not idx_list:
                    continue

            if n_verts <= 65535:
                idx_arr = array.array("H", idx_list)
                comp_type = 5123  # UNSIGNED_SHORT
            else:
                idx_arr = array.array("I", idx_list)
                comp_type = 5125  # UNSIGNED_INT
            bv_idx = _append_bv(idx_arr.tobytes(), 34963)  # ELEMENT_ARRAY_BUFFER
            idx_acc_idx = len(accessors)
            accessors.append(
                {
                    "bufferView": bv_idx,
                    "componentType": comp_type,
                    "count": len(idx_arr),
                    "type": "SCALAR",
                }
            )
            built_list.append((pos_acc_idx, idx_acc_idx, mat_sym))
        if built_list:
            geom_prims_built[gid] = built_list

    if not geom_prims_built:
        return None

    gltf_meshes: list[dict[str, Any]] = []
    mesh_idx_cache: dict[tuple[str, tuple[tuple[str, str], ...]], int] = {}

    def _get_gltf_mesh(gid: str, mat_bindings: dict[str, str]) -> int | None:
        prims = geom_prims_built.get(gid)
        if not prims:
            return None
        cache_key = (gid, tuple(sorted(mat_bindings.items())))
        existing = mesh_idx_cache.get(cache_key)
        if existing is not None:
            return existing
        gltf_prims: list[dict[str, Any]] = []
        for pos_acc_idx, idx_acc_idx, mat_sym in prims:
            prim_obj: dict[str, Any] = {
                "attributes": {"POSITION": pos_acc_idx},
                "indices": idx_acc_idx,
            }
            mat_id = mat_bindings.get(mat_sym or "", mat_sym or "")
            rgba = mat_colors_by_id.get(mat_id)
            m_idx = _get_material_idx(rgba)
            if m_idx is not None:
                prim_obj["material"] = m_idx
            gltf_prims.append(prim_obj)
        m_idx_out = len(gltf_meshes)
        gltf_meshes.append({"primitives": gltf_prims})
        mesh_idx_cache[cache_key] = m_idx_out
        return m_idx_out

    lib_nodes: dict[str, ET.Element] = {}
    for n in root.findall(f".//{pre}library_nodes//{pre}node", ns):
        nid = n.attrib.get("id")
        if nid:
            lib_nodes[nid] = n

    gltf_nodes: list[dict[str, Any]] = []

    def _build_node(node_el: ET.Element, depth: int = 0) -> int | None:
        if depth > 16:
            return None
        local_mat = _dae_node_local_matrix(node_el)
        child_indices: list[int] = []
        attached_meshes: list[int] = []

        for child in node_el:
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "node":
                c_idx = _build_node(child, depth + 1)
                if c_idx is not None:
                    child_indices.append(c_idx)
            elif tag == "instance_node":
                ref_id = (child.attrib.get("url") or "").lstrip("#")
                ref_el = lib_nodes.get(ref_id)
                if ref_el is not None:
                    c_idx = _build_node(ref_el, depth + 1)
                    if c_idx is not None:
                        child_indices.append(c_idx)
            elif tag == "instance_geometry":
                gid = (child.attrib.get("url") or "").lstrip("#")
                bindings: dict[str, str] = {}
                for im in child.findall(f".//{pre}instance_material", ns):
                    sym = im.attrib.get("symbol")
                    tgt = (im.attrib.get("target") or "").lstrip("#")
                    if sym and tgt:
                        bindings[sym] = tgt
                m_idx = _get_gltf_mesh(gid, bindings)
                if m_idx is not None:
                    attached_meshes.append(m_idx)

        if not attached_meshes and not child_indices:
            return None

        node_obj: dict[str, Any] = {}
        if local_mat != _mat4_identity():
            node_obj["matrix"] = _mat4_to_col_major(local_mat)
        if len(attached_meshes) == 1:
            node_obj["mesh"] = attached_meshes[0]
        elif len(attached_meshes) > 1:
            for m_idx in attached_meshes:
                sub_idx = len(gltf_nodes)
                gltf_nodes.append({"mesh": m_idx})
                child_indices.append(sub_idx)
        if child_indices:
            node_obj["children"] = child_indices

        idx = len(gltf_nodes)
        gltf_nodes.append(node_obj)
        return idx

    scene_root_children: list[int] = []
    visual_scene = root.find(f".//{pre}library_visual_scenes/{pre}visual_scene", ns)
    if visual_scene is not None:
        for child in visual_scene:
            if child.tag.rsplit("}", 1)[-1] == "node":
                n_idx = _build_node(child)
                if n_idx is not None:
                    scene_root_children.append(n_idx)

    # Fallback if visual_scene had no instance_geometry nodes: attach all geometries directly.
    if not scene_root_children:
        for gid in geom_prims_built:
            m_idx = _get_gltf_mesh(gid, {})
            if m_idx is not None:
                n_idx = len(gltf_nodes)
                gltf_nodes.append({"mesh": m_idx})
                scene_root_children.append(n_idx)

    if not scene_root_children:
        return None

    # Wrap in root node to apply Collada unit scaling only.
    # Do NOT bake <up_axis> rotation here: Gazebo Fuel & PX4 models (e.g. Fence.dae
    # in subt_tunnel_staging_area) rely on raw Collada coordinates matching how
    # Three.js ColladaLoader + scene.rotation.set(-PI/2, 0, 0) renders them.
    root_node: dict[str, Any] = {"children": scene_root_children}
    if abs(unit_scale - 1.0) > 1e-9:
        root_node["scale"] = [unit_scale, unit_scale, unit_scale]

    root_idx = len(gltf_nodes)
    gltf_nodes.append(root_node)

    end_pad = (-bin_offset) % 4
    if end_pad:
        bin_parts.append(b"\x00" * end_pad)
        bin_offset += end_pad
    bin_blob = b"".join(bin_parts)

    gltf: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": "s7gz-dae-geom"},
        "scene": 0,
        "scenes": [{"nodes": [root_idx]}],
        "nodes": gltf_nodes,
        "meshes": gltf_meshes,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(bin_blob)}],
    }
    if materials:
        gltf["materials"] = materials

    json_blob = json.dumps(gltf, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    json_pad = (-len(json_blob)) % 4
    if json_pad:
        json_blob += b" " * json_pad

    body = (
        struct.pack("<II", len(json_blob), _CHUNK_JSON)
        + json_blob
        + struct.pack("<II", len(bin_blob), _CHUNK_BIN)
        + bin_blob
    )
    header = struct.pack("<4sII", _GLB_MAGIC, 2, 12 + len(body))
    return header + body


def strip_glb_textures(raw: bytes) -> bytes:
    """Strip embedded images, textures, UVs, and tangents from a GLB 2.0 binary.

    Produces a valid, compact GLB containing only geometry + flat base colors
    so thumbnail loaders skip multi-megabyte image transfers and JPEG/PNG decodes.
    Falls back to the original bytes on any unexpected structure.
    """
    if len(raw) < 20 or raw[:4] != _GLB_MAGIC:
        return raw
    version, _total_len = struct.unpack_from("<II", raw, 4)
    if version != 2:
        return raw

    offset = 12
    json_bytes: bytes | None = None
    bin_bytes = b""
    while offset + 8 <= len(raw):
        chunk_len, chunk_type = struct.unpack_from("<II", raw, offset)
        offset += 8
        if offset + chunk_len > len(raw):
            return raw
        chunk_data = raw[offset : offset + chunk_len]
        offset += chunk_len
        if chunk_type == _CHUNK_JSON and json_bytes is None:
            json_bytes = chunk_data
        elif chunk_type == _CHUNK_BIN and not bin_bytes:
            bin_bytes = chunk_data

    if json_bytes is None:
        return raw

    try:
        gltf: dict[str, Any] = json.loads(json_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return raw

    # Bail out cleanly if buffers use external URIs rather than the embedded BIN chunk.
    buffers = gltf.get("buffers") or []
    if len(buffers) > 1 or (len(buffers) == 1 and buffers[0].get("uri")):
        return raw

    gltf.pop("images", None)
    gltf.pop("textures", None)
    gltf.pop("samplers", None)

    for ext_list_key in ("extensionsUsed", "extensionsRequired"):
        ext_list = gltf.get(ext_list_key)
        if isinstance(ext_list, list):
            kept = [
                e
                for e in ext_list
                if isinstance(e, str) and not e.startswith(_STRIPPED_EXT_PREFIXES)
            ]
            if kept:
                gltf[ext_list_key] = kept
            else:
                gltf.pop(ext_list_key, None)

    for mat in gltf.get("materials") or []:
        if not isinstance(mat, dict):
            continue
        for k in _STRIPPED_MAT_KEYS:
            mat.pop(k, None)
        pbr = mat.get("pbrMetallicRoughness")
        if isinstance(pbr, dict):
            had_mr_tex = "metallicRoughnessTexture" in pbr
            for k in _STRIPPED_PBR_KEYS:
                pbr.pop(k, None)
            if had_mr_tex:
                pbr["metallicFactor"] = min(float(pbr.get("metallicFactor", 0.2)), 0.25)
                pbr["roughnessFactor"] = max(float(pbr.get("roughnessFactor", 0.7)), 0.6)

    old_accessors: list[dict[str, Any]] = gltf.get("accessors") or []
    old_bvs: list[dict[str, Any]] = gltf.get("bufferViews") or []

    used_accessors: set[int] = set()
    used_bvs: set[int] = set()

    for mesh in gltf.get("meshes") or []:
        if not isinstance(mesh, dict):
            continue
        for prim in mesh.get("primitives") or []:
            if not isinstance(prim, dict):
                continue
            draco = (prim.get("extensions") or {}).get("KHR_draco_mesh_compression")
            has_draco = isinstance(draco, dict)
            if has_draco and isinstance(draco.get("bufferView"), int):
                used_bvs.add(draco["bufferView"])
            attrs = prim.get("attributes")
            if isinstance(attrs, dict):
                if not has_draco:
                    for key in list(attrs.keys()):
                        if key.startswith("TEXCOORD_") or key == "TANGENT":
                            attrs.pop(key, None)
                for acc_idx in attrs.values():
                    if isinstance(acc_idx, int):
                        used_accessors.add(acc_idx)
            if isinstance(prim.get("indices"), int):
                used_accessors.add(prim["indices"])
            for target in prim.get("targets") or []:
                if isinstance(target, dict):
                    for key in list(target.keys()):
                        if key == "TANGENT":
                            target.pop(key, None)
                    for acc_idx in target.values():
                        if isinstance(acc_idx, int):
                            used_accessors.add(acc_idx)

    for skin in gltf.get("skins") or []:
        if isinstance(skin, dict) and isinstance(skin.get("inverseBindMatrices"), int):
            used_accessors.add(skin["inverseBindMatrices"])

    # Drop animations for static thumbnail geometry.
    gltf.pop("animations", None)

    for acc_idx in used_accessors:
        if 0 <= acc_idx < len(old_accessors):
            acc = old_accessors[acc_idx]
            if isinstance(acc.get("bufferView"), int):
                used_bvs.add(acc["bufferView"])
            sparse = acc.get("sparse")
            if isinstance(sparse, dict):
                s_idx = sparse.get("indices")
                s_val = sparse.get("values")
                if isinstance(s_idx, dict) and isinstance(s_idx.get("bufferView"), int):
                    used_bvs.add(s_idx["bufferView"])
                if isinstance(s_val, dict) and isinstance(s_val.get("bufferView"), int):
                    used_bvs.add(s_val["bufferView"])

    # Compact bufferViews & rebuild 4-byte aligned BIN chunk (zero-copy via memoryview).
    bin_view = memoryview(bin_bytes)
    bv_remap: dict[int, int] = {}
    new_bvs: list[dict[str, Any]] = []
    bin_parts: list[bytes | memoryview] = []
    new_bin_offset = 0

    for old_idx in sorted(used_bvs):
        if not (0 <= old_idx < len(old_bvs)):
            return raw
        bv = dict(old_bvs[old_idx])
        src_offset = int(bv.get("byteOffset", 0))
        byte_len = int(bv.get("byteLength", 0))
        if src_offset < 0 or byte_len < 0 or src_offset + byte_len > len(bin_view):
            return raw
        pad = (-new_bin_offset) % 4
        if pad:
            bin_parts.append(b"\x00" * pad)
            new_bin_offset += pad
        bv["byteOffset"] = new_bin_offset
        bv_remap[old_idx] = len(new_bvs)
        new_bvs.append(bv)
        bin_parts.append(bin_view[src_offset : src_offset + byte_len])
        new_bin_offset += byte_len

    end_pad = (-new_bin_offset) % 4
    if end_pad:
        bin_parts.append(b"\x00" * end_pad)
        new_bin_offset += end_pad

    new_bin = b"".join(bin_parts)

    # Compact accessors & remap all references.
    acc_remap: dict[int, int] = {}
    new_accessors: list[dict[str, Any]] = []
    for old_idx in sorted(used_accessors):
        if not (0 <= old_idx < len(old_accessors)):
            return raw
        acc = dict(old_accessors[old_idx])
        if isinstance(acc.get("bufferView"), int):
            acc["bufferView"] = bv_remap[acc["bufferView"]]
        sparse = acc.get("sparse")
        if isinstance(sparse, dict):
            sparse = dict(sparse)
            if isinstance(sparse.get("indices"), dict):
                s_idx = dict(sparse["indices"])
                if isinstance(s_idx.get("bufferView"), int):
                    s_idx["bufferView"] = bv_remap[s_idx["bufferView"]]
                sparse["indices"] = s_idx
            if isinstance(sparse.get("values"), dict):
                s_val = dict(sparse["values"])
                if isinstance(s_val.get("bufferView"), int):
                    s_val["bufferView"] = bv_remap[s_val["bufferView"]]
                sparse["values"] = s_val
            acc["sparse"] = sparse
        acc_remap[old_idx] = len(new_accessors)
        new_accessors.append(acc)

    for mesh in gltf.get("meshes") or []:
        if not isinstance(mesh, dict):
            continue
        for prim in mesh.get("primitives") or []:
            if not isinstance(prim, dict):
                continue
            draco = (prim.get("extensions") or {}).get("KHR_draco_mesh_compression")
            if isinstance(draco, dict) and isinstance(draco.get("bufferView"), int):
                draco["bufferView"] = bv_remap[draco["bufferView"]]
            attrs = prim.get("attributes")
            if isinstance(attrs, dict):
                for key, old_idx in list(attrs.items()):
                    if isinstance(old_idx, int):
                        attrs[key] = acc_remap[old_idx]
            if isinstance(prim.get("indices"), int):
                prim["indices"] = acc_remap[prim["indices"]]
            for target in prim.get("targets") or []:
                if isinstance(target, dict):
                    for key, old_idx in list(target.items()):
                        if isinstance(old_idx, int):
                            target[key] = acc_remap[old_idx]

    for skin in gltf.get("skins") or []:
        if isinstance(skin, dict) and isinstance(skin.get("inverseBindMatrices"), int):
            skin["inverseBindMatrices"] = acc_remap[skin["inverseBindMatrices"]]

    gltf["accessors"] = new_accessors
    gltf["bufferViews"] = new_bvs
    if new_bin:
        gltf["buffers"] = [{"byteLength": len(new_bin)}]
    else:
        gltf.pop("buffers", None)

    new_json = json.dumps(gltf, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    json_pad = (-len(new_json)) % 4
    if json_pad:
        new_json += b" " * json_pad

    chunks = [struct.pack("<II", len(new_json), _CHUNK_JSON), new_json]
    if new_bin:
        chunks.extend([struct.pack("<II", len(new_bin), _CHUNK_BIN), new_bin])

    body = b"".join(chunks)
    header = struct.pack("<4sII", _GLB_MAGIC, 2, 12 + len(body))
    return header + body


__all__ = [
    "dae_to_geometry_glb",
    "find_asset_thumbnail",
    "find_model_thumbnail_url",
    "find_world_thumbnail_url",
    "strip_dae_images",
    "strip_glb_textures",
]
