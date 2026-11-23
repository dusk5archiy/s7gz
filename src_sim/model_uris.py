from __future__ import annotations

import re
import shutil
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import unquote

from src_sim.fuel.fs import atomic_path
from src_sim.fuel.ignition_plugin_transforms import IgnitionPluginTransform
from src_sim.settings.resource import ResourceSettings

_SDF_TAG_RE = re.compile(r"<sdf\b([^>]*)>", re.IGNORECASE)
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_URI_ELEMENT_TAGS = {
    "uri",
    "albedo_map",
    "normal_map",
    "roughness_map",
    "metalness_map",
    "emissive_map",
    "diffuse",
    "normal",
}
_RUNTIME_TOP_DIRS = ("generated_models", "patched_models", "source_models")
_FILE_RUNTIME_MARKER_RE = re.compile(
    r"/(source_models|patched_models|generated_models)/(.+)$"
)


def to_runtime_model_uri(
    target: Path, *, resource: ResourceSettings, trailing_slash: bool = False
) -> str:
    """Build a portable `model://<rel>` URI rooted at `resource.runtime_dir` (no `%20` encoding)."""
    runtime_root = resource.runtime_dir.resolve()
    resolved = target.resolve()
    if not resolved.is_relative_to(runtime_root):
        raise ValueError(
            f"Path {resolved} is outside runtime_dir {runtime_root} and cannot be expressed as runtime model:// URI"
        )
    rel = resolved.relative_to(runtime_root).as_posix()
    suffix = "/" if trailing_slash and not rel.endswith("/") else ""
    return f"model://{rel}{suffix}"


def infer_provider_from_path(
    path: Path, *, resource: ResourceSettings
) -> str | None:
    resolved = path.resolve()
    for base in (
        resource.source_worlds_dir.resolve(),
        resource.patched_worlds_dir.resolve(),
        resource.source_models_dir.resolve(),
        resource.patched_models_dir.resolve(),
    ):
        if resolved.is_relative_to(base):
            rel_parts = resolved.relative_to(base).parts
            if rel_parts:
                return rel_parts[0]
    return None


def parse_sdf_xml_with_ns_fix(xml_text: str) -> ET.Element:
    cleaned = xml_text.lstrip()
    try:
        return ET.fromstring(cleaned)
    except ET.ParseError:
        def _add_ns(match: re.Match[str]) -> str:
            attrs = match.group(1)
            extra = ""
            if "xmlns:gz=" not in attrs:
                extra += ' xmlns:gz="http://gazebosim.org/schema"'
            if "xmlns:ignition=" not in attrs:
                extra += ' xmlns:ignition="http://ignitionrobotics.org/schema"'
            return f"<sdf{attrs}{extra}>"

        return ET.fromstring(_SDF_TAG_RE.sub(_add_ns, cleaned, count=1))


def render_sdf_xml(root: ET.Element) -> str:
    ET.indent(root, space="  ")
    return '<?xml version="1.0" ?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def _is_model_package_dir(path: Path) -> bool:
    return path.is_dir() and (
        (path / "model.sdf").is_file() or (path / "model.config").is_file()
    )


def _normalize_model_key(name: str) -> str:
    return re.sub(r"[\s_-]+", " ", name.strip().lower())


def _resolve_existing_path(base: Path, rel: str) -> Path | None:
    """Resolve `base / rel` trying raw text first, then URL-unquoted text."""
    base_res = base.resolve()
    for cand_rel in (rel, unquote(rel)):
        cleaned = cand_rel.strip().strip("/")
        if not cleaned or "\\" in cleaned or ".." in cleaned.split("/"):
            continue
        cand = (base_res / cleaned).resolve()
        if cand.is_relative_to(base_res) and cand.exists():
            return cand
    return None


def _split_provider_and_model_rel(
    target_dir: Path, *, models_root: Path
) -> tuple[str, str] | None:
    root_res = models_root.resolve()
    resolved = target_dir.resolve()
    if not resolved.is_relative_to(root_res):
        return None
    parts = resolved.relative_to(root_res).parts
    if len(parts) < 2:
        return None
    return parts[0], "/".join(parts[1:])


def _resolve_sdf_entries(model_dir: Path) -> list[str]:
    """Return relative SDF filenames referenced by `model.config` (falling back to `model.sdf`)."""
    entries: list[str] = []
    config_file = model_dir / "model.config"
    if config_file.is_file():
        try:
            cfg_root = ET.fromstring(
                config_file.read_text(encoding="utf-8", errors="replace").lstrip()
            )
            for sdf_el in cfg_root.findall("sdf"):
                rel = (sdf_el.text or "").strip()
                if rel and (model_dir / rel).is_file() and rel not in entries:
                    entries.append(rel)
        except ET.ParseError:
            pass
    if not entries and (model_dir / "model.sdf").is_file():
        entries.append("model.sdf")
    return entries


def _build_default_model_config(*, model_name: str, sdf_rel: str, sdf_version: str) -> str:
    root = ET.Element("model")
    ET.SubElement(root, "name").text = model_name
    ET.SubElement(root, "version").text = "1.0"
    ET.SubElement(root, "sdf", version=sdf_version).text = sdf_rel
    return render_sdf_xml(root)


def canonicalize_sdf_element_uris(
    root: ET.Element,
    *,
    resource: ResourceSettings,
    provider: str | None = None,
    src_model_dir: Path | None = None,
    external_model_uri_prefix: str | None = None,
) -> set[tuple[str, str]]:
    """Rewrite URIs inside `root` to canonical `model://<runtime_subpath>` form.

    Returns a set of `(provider, model_rel)` dependencies that should have lightweight
    wrappers ensured under `patched_models/<provider>/<model_rel>`.
    """
    runtime_root = resource.runtime_dir.resolve()
    source_models_root = resource.source_models_dir.resolve()
    patched_models_root = resource.patched_models_dir.resolve()
    resolved_src_model = src_model_dir.resolve() if src_model_dir is not None else None

    self_model_names: set[str] = set()
    if resolved_src_model is not None:
        self_model_names.add(_normalize_model_key(resolved_src_model.name))
        if resolved_src_model.name.isdigit() and resolved_src_model.parent.name:
            self_model_names.add(_normalize_model_key(resolved_src_model.parent.name))
    model_el = root if root.tag == "model" else root.find("model")
    if model_el is not None and model_el.attrib.get("name"):
        self_model_names.add(_normalize_model_key(model_el.attrib["name"]))

    deps: set[tuple[str, str]] = set()

    def _record_dep_from_source(model_dir: Path) -> str:
        split = _split_provider_and_model_rel(model_dir, models_root=source_models_root)
        if split is not None:
            dep_prov, dep_rel = split
            deps.add((dep_prov, dep_rel))
            return to_runtime_model_uri(
                patched_models_root / dep_prov / dep_rel,
                resource=resource,
            )
        return to_runtime_model_uri(model_dir, resource=resource)

    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag not in _URI_ELEMENT_TAGS or not el.text:
            continue
        raw = el.text.strip()
        if not raw:
            continue
        had_trailing_slash = raw.endswith("/")

        # 1. Legacy file:// URI pointing into runtime/{source_models,patched_models,generated_models}/...
        if raw.startswith("file://"):
            decoded_path = unquote(raw.removeprefix("file://"))
            m = _FILE_RUNTIME_MARKER_RE.search(decoded_path)
            if not m:
                continue
            bucket, sub = m.group(1), m.group(2).strip("/")
            if bucket == "generated_models":
                el.text = f"model://generated_models/{sub}" + ("/" if had_trailing_slash else "")
                continue
            cand_src = _resolve_existing_path(source_models_root, sub)
            if cand_src is not None:
                if _is_model_package_dir(cand_src):
                    el.text = _record_dep_from_source(cand_src)
                else:
                    el.text = to_runtime_model_uri(
                        cand_src, resource=resource, trailing_slash=had_trailing_slash
                    )
                continue
            cand_pat = _resolve_existing_path(patched_models_root, sub)
            if cand_pat is not None:
                el.text = to_runtime_model_uri(
                    cand_pat, resource=resource, trailing_slash=had_trailing_slash
                )
            continue

        # 2. model:// URI
        if raw.startswith("model://"):
            rest = raw.removeprefix("model://").strip()
            if not rest:
                continue
            rest_clean = rest.strip("/")
            first_seg = rest_clean.split("/", 1)[0]

            # 2a. Already rooted at runtime_dir (generated_models/, patched_models/, source_models/)
            if first_seg in _RUNTIME_TOP_DIRS:
                rest_unquoted = unquote(rest_clean) if "%" in rest_clean else rest_clean
                if first_seg == "patched_models":
                    sub_after_bucket = rest_unquoted.removeprefix("patched_models/").strip("/")
                    cand_src = _resolve_existing_path(source_models_root, sub_after_bucket)
                    if cand_src is not None and _is_model_package_dir(cand_src):
                        el.text = _record_dep_from_source(cand_src)
                        continue
                # Normalize any %20 encoding if the unquoted path exists on disk
                cand_rt = _resolve_existing_path(runtime_root, rest_clean)
                if cand_rt is not None:
                    el.text = to_runtime_model_uri(
                        cand_rt, resource=resource, trailing_slash=had_trailing_slash
                    )
                continue

            # 2b. Provider-prefixed model://<provider>/... (e.g. model://px4/x500_base or model://fuel/...)
            if first_seg in {"px4", "fuel"} and "/" in rest_clean:
                cand_src = _resolve_existing_path(source_models_root, rest_clean)
                if cand_src is not None:
                    if _is_model_package_dir(cand_src):
                        el.text = _record_dep_from_source(cand_src)
                    else:
                        el.text = to_runtime_model_uri(
                            cand_src, resource=resource, trailing_slash=had_trailing_slash
                        )
                    continue
                cand_pat = _resolve_existing_path(patched_models_root, rest_clean)
                if cand_pat is not None:
                    el.text = to_runtime_model_uri(
                        cand_pat, resource=resource, trailing_slash=had_trailing_slash
                    )
                    continue

            # 2c. Self-reference inside a model: e.g. `model://Oak tree/meshes/oak_tree.dae`
            # or `model://x500_base/meshes/NXP-HGD-CF.dae`
            if resolved_src_model is not None and "/" in rest_clean:
                ref_name, ref_sub = rest_clean.split("/", 1)
                if _normalize_model_key(unquote(ref_name)) in self_model_names:
                    cand_self = _resolve_existing_path(resolved_src_model, ref_sub)
                    if cand_self is not None:
                        if cand_self.is_relative_to(runtime_root):
                            el.text = to_runtime_model_uri(
                                cand_self,
                                resource=resource,
                                trailing_slash=had_trailing_slash,
                            )
                            continue
                        if external_model_uri_prefix and cand_self.is_relative_to(
                            resolved_src_model
                        ):
                            rel = cand_self.relative_to(resolved_src_model).as_posix()
                            suffix = "/" if had_trailing_slash else ""
                            el.text = f"model://{external_model_uri_prefix}/{rel}{suffix}"
                            continue

            # 2d. Provider-scoped lookup: inside `px4` (or another provider), `model://<pkg>` or `model://<pkg>/<subpath>`
            if provider:
                prov_src = source_models_root / provider
                prov_pat = patched_models_root / provider
                cand_src = _resolve_existing_path(prov_src, rest_clean) if prov_src.is_dir() else None
                if cand_src is not None:
                    if _is_model_package_dir(cand_src):
                        el.text = _record_dep_from_source(cand_src)
                    else:
                        el.text = to_runtime_model_uri(
                            cand_src, resource=resource, trailing_slash=had_trailing_slash
                        )
                    continue
                cand_pat = _resolve_existing_path(prov_pat, rest_clean) if prov_pat.is_dir() else None
                if cand_pat is not None:
                    el.text = to_runtime_model_uri(
                        cand_pat, resource=resource, trailing_slash=had_trailing_slash
                    )
                    continue

            # 2e. Last-resort self-reference check (some Fuel models use a different casing/alias
            # in `model://<alias>/<subpath>` even though `<subpath>` lives directly inside `src_model_dir`).
            if resolved_src_model is not None and "/" in rest_clean:
                _, ref_sub = rest_clean.split("/", 1)
                cand_self = _resolve_existing_path(resolved_src_model, ref_sub)
                if cand_self is not None and cand_self.is_relative_to(runtime_root):
                    el.text = to_runtime_model_uri(
                        cand_self, resource=resource, trailing_slash=had_trailing_slash
                    )
                    continue

            continue

        # 3. Other schemes (http://, https://, package://) or absolute filesystem paths: leave alone
        if _SCHEME_RE.match(raw) or raw.startswith("/"):
            continue

        # 4. Relative local asset URI inside a model (e.g. `base_visual.glb`, `meshes/body.dae`)
        if resolved_src_model is not None:
            cand_rel = _resolve_existing_path(resolved_src_model, raw)
            if cand_rel is not None:
                if cand_rel.is_relative_to(runtime_root):
                    el.text = to_runtime_model_uri(
                        cand_rel, resource=resource, trailing_slash=had_trailing_slash
                    )
                elif external_model_uri_prefix and cand_rel.is_relative_to(
                    resolved_src_model
                ):
                    rel = cand_rel.relative_to(resolved_src_model).as_posix()
                    suffix = "/" if had_trailing_slash else ""
                    el.text = f"model://{external_model_uri_prefix}/{rel}{suffix}"

    return deps


def write_lightweight_model_wrapper(
    provider: str,
    model_rel: str,
    *,
    resource: ResourceSettings,
    visited: set[tuple[str, str]] | None = None,
) -> Path:
    """Create/refresh a lightweight patched model wrapper (only `model.config` + patched SDF).

    All meshes/textures remain in `source_models/` and are referenced via portable
    `model://source_models/...` URIs. Nested model dependencies are patched recursively.
    """
    from src_sim.fuel.uri_localizers.production import ProductionFuelUriLocalizer

    cleaned_rel = model_rel.strip().strip("/")
    key = (provider, cleaned_rel)
    active_visited = visited if visited is not None else set()

    source_models_root = resource.source_models_dir.resolve()
    patched_models_root = resource.patched_models_dir.resolve()
    src_dir = (source_models_root / provider / cleaned_rel).resolve()
    dst_dir = (patched_models_root / provider / cleaned_rel).resolve()

    if not src_dir.is_relative_to(source_models_root / provider) or not src_dir.is_dir():
        raise FileNotFoundError(
            f"Source model directory not found: {provider}/{cleaned_rel}"
        )
    if not dst_dir.is_relative_to(patched_models_root / provider):
        raise ValueError(f"Invalid patched model destination: {provider}/{cleaned_rel}")

    if key in active_visited:
        return dst_dir
    active_visited.add(key)

    sdf_entries = _resolve_sdf_entries(src_dir)
    if not sdf_entries:
        raise FileNotFoundError(
            f"No model.sdf found in source model directory: {src_dir}"
        )

    fuel_localizer = ProductionFuelUriLocalizer(s_resource=resource)
    plugin_transform = IgnitionPluginTransform()

    rendered_sdfs: dict[str, str] = {}
    all_deps: set[tuple[str, str]] = set()
    primary_version = "1.9"

    for idx, sdf_rel in enumerate(sdf_entries):
        src_sdf = src_dir / sdf_rel
        raw_text = src_sdf.read_text(encoding="utf-8", errors="replace")
        localized_text = plugin_transform(fuel_localizer(raw_text))
        root = parse_sdf_xml_with_ns_fix(localized_text)
        if idx == 0:
            primary_version = root.get("version") or "1.9"
        deps = canonicalize_sdf_element_uris(
            root,
            resource=resource,
            provider=provider,
            src_model_dir=src_dir,
        )
        all_deps.update(deps)
        rendered_sdfs[sdf_rel] = render_sdf_xml(root)

    # Replace destination cleanly so no stale heavy mesh copies remain from earlier runs.
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    src_config = src_dir / "model.config"
    if src_config.is_file():
        shutil.copy2(src_config, dst_dir / "model.config")
    else:
        default_name = (
            src_dir.parent.name if src_dir.name.isdigit() else src_dir.name
        )
        with atomic_path(dst_dir / "model.config") as tmp_cfg:
            tmp_cfg.write_text(
                _build_default_model_config(
                    model_name=default_name,
                    sdf_rel=sdf_entries[0],
                    sdf_version=primary_version,
                ),
                encoding="utf-8",
            )

    for sdf_rel, xml_out in rendered_sdfs.items():
        out_sdf = dst_dir / sdf_rel
        with atomic_path(out_sdf) as tmp_sdf:
            tmp_sdf.write_text(xml_out, encoding="utf-8")

    # Recursively ensure all transitive model dependencies.
    for dep_prov, dep_rel in sorted(all_deps):
        if (dep_prov, dep_rel) in active_visited:
            continue
        try:
            write_lightweight_model_wrapper(
                dep_prov,
                dep_rel,
                resource=resource,
                visited=active_visited,
            )
        except (FileNotFoundError, ValueError):
            continue

    return dst_dir


def ensure_model_wrappers(
    deps: Iterable[tuple[str, str]],
    *,
    resource: ResourceSettings,
) -> int:
    """Ensure lightweight patched wrappers exist for all `(provider, model_rel)` pairs."""
    visited: set[tuple[str, str]] = set()
    count = 0
    for prov, rel in sorted(set(deps)):
        if (prov, rel) in visited:
            continue
        try:
            before = len(visited)
            write_lightweight_model_wrapper(
                prov, rel, resource=resource, visited=visited
            )
            count += len(visited) - before
        except (FileNotFoundError, ValueError):
            continue
    return count


__all__ = [
    "canonicalize_sdf_element_uris",
    "ensure_model_wrappers",
    "infer_provider_from_path",
    "parse_sdf_xml_with_ns_fix",
    "render_sdf_xml",
    "to_runtime_model_uri",
    "write_lightweight_model_wrapper",
]
