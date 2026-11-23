from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_DAE_INIT_FROM_RE = re.compile(r"<init_from>\s*([^<\s][^<]*?)\s*</init_from>", re.IGNORECASE)

_SDF_ASSET_XPATHS = (
    ".//mesh/uri",
    ".//heightmap/uri",
    ".//heightmap/texture/diffuse",
    ".//heightmap/texture/normal",
    ".//material/pbr/metal/albedo_map",
    ".//material/pbr/metal/normal_map",
    ".//material/pbr/metal/roughness_map",
    ".//material/pbr/metal/metalness_map",
    ".//material/pbr/metal/emissive_map",
)


def _strip_local_uri(raw_uri: str, model_dir: Path) -> str | None:
    cleaned = unquote(raw_uri.strip())
    if not cleaned:
        return None
    if cleaned.startswith("model://"):
        rest = cleaned.removeprefix("model://")
        parts = rest.split("/", 1)
        if len(parts) != 2 or not parts[1]:
            return None
        model_name, subpath = parts
        # Only verify model:// URIs that refer to this model directory itself.
        if model_name.lower() != model_dir.parent.name.lower():
            return None
        return subpath.lstrip("/")
    if _SCHEME_RE.match(cleaned) or cleaned.startswith("/"):
        return None
    return cleaned


def _resolve_sdf_entry(version_dir: Path) -> Path | None:
    config_file = version_dir / "model.config"
    if config_file.is_file():
        try:
            root = ET.fromstring(config_file.read_text(encoding="utf-8", errors="replace").lstrip())
            for sdf_el in root.findall("sdf"):
                if sdf_el.text and sdf_el.text.strip():
                    cand = (version_dir / sdf_el.text.strip()).resolve()
                    if cand.is_relative_to(version_dir.resolve()):
                        return cand
        except ET.ParseError:
            pass
    default_sdf = version_dir / "model.sdf"
    if default_sdf.is_file():
        return default_sdf
    sdfs = sorted(version_dir.glob("*.sdf"))
    return sdfs[0] if sdfs else None


def find_missing_asset_files(
    version_dir: Path,
    *,
    check_dae_textures: bool = True,
    runtime_dir: Path | None = None,
) -> list[str]:
    """Return relative paths of local SDF/mesh/texture files missing inside `version_dir`."""
    resolved_root = version_dir.resolve()
    resolved_runtime = runtime_dir.resolve() if runtime_dir is not None else None
    if not resolved_root.is_dir():
        return ["<missing_dir>"]

    sdf_path = _resolve_sdf_entry(resolved_root)
    if sdf_path is None or not sdf_path.is_file():
        return ["model.sdf"]

    try:
        sdf_root = ET.fromstring(sdf_path.read_text(encoding="utf-8", errors="replace").lstrip())
    except ET.ParseError:
        return [sdf_path.relative_to(resolved_root).as_posix()]

    missing: list[str] = []
    seen_missing: set[str] = set()
    dae_files: list[Path] = []

    def _record_missing(rel_label: str) -> None:
        if rel_label not in seen_missing:
            seen_missing.add(rel_label)
            missing.append(rel_label)

    for xpath in _SDF_ASSET_XPATHS:
        for el in sdf_root.findall(xpath):
            if not el.text:
                continue
            raw_text = el.text.strip()
            if (
                resolved_runtime is not None
                and raw_text.startswith(("model://source_models/", "model://patched_models/"))
            ):
                rt_sub = raw_text.removeprefix("model://").strip("/")
                rt_target = (resolved_runtime / rt_sub).resolve()
                if not rt_target.is_relative_to(resolved_runtime):
                    continue
                if not rt_target.exists():
                    _record_missing(rt_sub)
                elif check_dae_textures and rt_target.is_file() and rt_target.suffix.lower() == ".dae":
                    dae_files.append(rt_target)
                continue
            rel = _strip_local_uri(raw_text, resolved_root)
            if not rel:
                continue
            target = (resolved_root / rel).resolve()
            if not target.is_relative_to(resolved_root):
                continue
            if not target.exists():
                _record_missing(rel)
            elif check_dae_textures and target.is_file() and target.suffix.lower() == ".dae":
                dae_files.append(target)

    for dae_path in dae_files:
        dae_base = resolved_runtime if (resolved_runtime is not None and dae_path.is_relative_to(resolved_runtime)) else resolved_root
        try:
            dae_text = dae_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            _record_missing(dae_path.relative_to(dae_base).as_posix())
            continue
        for match in _DAE_INIT_FROM_RE.finditer(dae_text):
            raw_ref = unquote(match.group(1).strip())
            if not raw_ref or _SCHEME_RE.match(raw_ref) or raw_ref.startswith("/"):
                continue
            # Collada <surface><init_from> references <image id="..."> (no extension or slash)
            if "." not in Path(raw_ref).name and "/" not in raw_ref:
                continue
            tex_path = (dae_path.parent / raw_ref).resolve()
            if not tex_path.is_relative_to(dae_base):
                continue
            if not tex_path.is_file():
                _record_missing(tex_path.relative_to(dae_base).as_posix())

    return missing


__all__ = ["find_missing_asset_files"]
