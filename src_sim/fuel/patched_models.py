from __future__ import annotations

from collections import deque
import shutil
from pathlib import Path
from urllib.parse import unquote

from src_sim.settings.resource import ResourceSettings

from .asset_ensurers.production import ProductionAssetEnsurer
from .cache_integrity import find_missing_asset_files
from .cache_resolvers.production import ProductionCacheResolver
from .models import FuelAssetRef
from .progress import emit_fuel_progress
from .uri_rules.production import ProductionFuelUriRule
from .world_dependency_syncers.production import ProductionWorldDependencySyncer
from .world_dependency_syncers.standard import FUEL_TEXT_EXTENSIONS


def asset_ref_from_rel_path(relative_path: str) -> FuelAssetRef:
    parts = [p for p in relative_path.strip().strip("/").split("/") if p]
    if len(parts) < 5 or parts[2] != "models":
        raise ValueError(f"Cannot infer FuelAssetRef from path: {relative_path!r}")
    return FuelAssetRef(
        server=unquote(parts[0]),
        owner=unquote(parts[1]),
        asset_kind="models",
        name=unquote(parts[3]),
    )


def ensure_complete_source_model(
    relative_path: str, *, resource: ResourceSettings
) -> tuple[Path, bool]:
    """Ensure source model in `fuel_cache_dir` exists and has no missing local files."""
    cleaned = relative_path.strip().lstrip("/")
    if not cleaned or "\\" in cleaned or ".." in cleaned.split("/"):
        raise ValueError(f"Invalid model path: {relative_path!r}")

    cache_root = resource.source_models_of("fuel").resolve()
    src_dir = (cache_root / cleaned).resolve()
    if not src_dir.is_relative_to(cache_root) or not src_dir.is_dir():
        src_dir = None

    repaired = False
    if src_dir is None or find_missing_asset_files(src_dir):
        if src_dir is not None and src_dir.exists():
            shutil.rmtree(src_dir)
        ref = asset_ref_from_rel_path(cleaned)
        src_dir = ProductionAssetEnsurer()(ref)
        repaired = True

    return src_dir, repaired


def _extract_model_rel_paths_from_text(
    text: str,
    *,
    cache_root: Path,
    patched_root: Path | None,
    cache_resolver: ProductionCacheResolver,
    uri_rule: ProductionFuelUriRule,
) -> set[str]:
    rel_paths: set[str] = set()
    for match in uri_rule.find_all(text=text):
        if match.asset.asset_kind != "models":
            continue
        resolved_dir = cache_resolver.resolve(asset=match.asset)
        if resolved_dir is not None and resolved_dir.resolve().is_relative_to(cache_root):
            rel_paths.add(resolved_dir.resolve().relative_to(cache_root).as_posix())

    roots = [cache_root]
    if patched_root is not None:
        roots.append(patched_root)
    for root in roots:
        prefix = f"{root.as_posix()}/"
        start = 0
        while True:
            idx = text.find(prefix, start)
            if idx == -1:
                break
            end = idx + len(prefix)
            while end < len(text) and text[end] not in "<\"'\r\n":
                end += 1
            sub = unquote(text[idx + len(prefix) : end]).strip().strip("/")
            parts = [p.strip() for p in sub.split("/") if p.strip()]
            if len(parts) >= 5 and parts[2] == "models":
                rel_paths.add("/".join(parts[:5]))
            start = end
    return rel_paths


def _scan_dir_model_rel_paths(
    asset_dir: Path,
    *,
    cache_root: Path,
    patched_root: Path | None,
    cache_resolver: ProductionCacheResolver,
    uri_rule: ProductionFuelUriRule,
) -> set[str]:
    found: set[str] = set()
    if not asset_dir.is_dir():
        return found
    for path in sorted(asset_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in FUEL_TEXT_EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        found.update(
            _extract_model_rel_paths_from_text(
                text,
                cache_root=cache_root,
                patched_root=patched_root,
                cache_resolver=cache_resolver,
                uri_rule=uri_rule,
            )
        )
    return found


def _expand_model_closure_rel_paths(
    initial_rel_paths: set[str],
    *,
    cache_root: Path,
    patched_root: Path | None,
    cache_resolver: ProductionCacheResolver,
    uri_rule: ProductionFuelUriRule,
) -> list[str]:
    visited: set[str] = set(initial_rel_paths)
    queue: deque[str] = deque(sorted(initial_rel_paths))
    while queue:
        rel = queue.popleft()
        model_dir = (cache_root / rel).resolve()
        if not model_dir.is_relative_to(cache_root) or not model_dir.is_dir():
            continue
        for dep_rel in sorted(
            _scan_dir_model_rel_paths(
                model_dir,
                cache_root=cache_root,
                patched_root=patched_root,
                cache_resolver=cache_resolver,
                uri_rule=uri_rule,
            )
        ):
            if dep_rel not in visited:
                visited.add(dep_rel)
                queue.append(dep_rel)
    return sorted(visited)


def patch_fuel_model(
    relative_path: str,
    *,
    resource: ResourceSettings,
    emit_steps: bool = True,
    include_dependencies: bool = True,
) -> bool:
    """Copy a Fuel model into `patched_models_dir` (repairing cache if incomplete) and patch it."""
    cache_root = resource.source_models_of("fuel").resolve()
    patched_root = resource.patched_models_of("fuel").resolve()
    cleaned_rel = relative_path.strip().lstrip("/")
    if emit_steps:
        emit_fuel_progress(
            f"[1/3] Verifying source cache: {cleaned_rel}",
            kind="model_verify",
            done=1,
            total=3,
        )
    src_dir, repaired = ensure_complete_source_model(cleaned_rel, resource=resource)

    dst_dir = (patched_root / cleaned_rel).resolve()
    if not dst_dir.is_relative_to(patched_root):
        raise ValueError(f"Invalid patched model destination: {relative_path!r}")

    if emit_steps:
        emit_fuel_progress(
            f"[2/3] Copying to patched_models: {cleaned_rel}",
            kind="model_copy",
            done=2,
            total=3,
        )
    if src_dir != dst_dir:
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        dst_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_dir, dst_dir)

    sdf_path = dst_dir / "model.sdf"
    if not sdf_path.is_file():
        raise FileNotFoundError(f"model.sdf not found for {relative_path!r}")
    if emit_steps:
        emit_fuel_progress(
            f"[3/3] Syncing dependencies & rewriting URIs: {cleaned_rel}",
            kind="model_sync",
            done=3,
            total=3,
        )
    ProductionWorldDependencySyncer()(x=sdf_path)

    if include_dependencies:
        cache_resolver = ProductionCacheResolver()
        uri_rule = ProductionFuelUriRule()
        direct_deps = _scan_dir_model_rel_paths(
            dst_dir,
            cache_root=cache_root,
            patched_root=patched_root,
            cache_resolver=cache_resolver,
            uri_rule=uri_rule,
        )
        direct_deps.discard(cleaned_rel)
        all_deps = [
            dep
            for dep in _expand_model_closure_rel_paths(
                direct_deps,
                cache_root=cache_root,
                patched_root=patched_root,
                cache_resolver=cache_resolver,
                uri_rule=uri_rule,
            )
            if dep != cleaned_rel
        ]
        for idx, dep_rel in enumerate(all_deps, start=1):
            try:
                patch_fuel_model(
                    dep_rel,
                    resource=resource,
                    emit_steps=False,
                    include_dependencies=False,
                )
                if emit_steps:
                    emit_fuel_progress(
                        f"[{idx}/{len(all_deps)}] Patched nested model: {dep_rel}",
                        kind="model_patch",
                        done=idx,
                        total=len(all_deps),
                    )
            except (FileNotFoundError, ValueError):
                continue

    return repaired


def sync_world_models_to_patched(
    sdf_paths: list[Path], *, resource: ResourceSettings
) -> int:
    """Ensure and patch all Fuel models (including nested dependencies) referenced by `sdf_paths`."""
    cache_root = resource.source_models_of("fuel").resolve()
    patched_root = resource.patched_models_of("fuel").resolve()
    cache_resolver = ProductionCacheResolver()
    uri_rule = ProductionFuelUriRule()
    direct_rels: set[str] = set()

    for sdf_path in sdf_paths:
        if not sdf_path.is_file():
            continue
        text = sdf_path.read_text(encoding="utf-8", errors="replace")
        direct_rels.update(
            _extract_model_rel_paths_from_text(
                text,
                cache_root=cache_root,
                patched_root=patched_root,
                cache_resolver=cache_resolver,
                uri_rule=uri_rule,
            )
        )

    sorted_rels = _expand_model_closure_rel_paths(
        direct_rels,
        cache_root=cache_root,
        patched_root=patched_root,
        cache_resolver=cache_resolver,
        uri_rule=uri_rule,
    )
    seen: set[str] = set(sorted_rels)
    queue: deque[str] = deque(sorted_rels)
    total = len(queue)
    if total:
        emit_fuel_progress(
            f"Patching {total} dependent model(s) into patched_models...",
            kind="model_patch_start",
            done=0,
            total=total,
        )
    patched_count = 0
    idx = 0
    while queue:
        rel = queue.popleft()
        idx += 1
        try:
            patch_fuel_model(
                rel,
                resource=resource,
                emit_steps=False,
                include_dependencies=False,
            )
            patched_count += 1
            dst_dir = (patched_root / rel).resolve()
            if dst_dir.is_relative_to(patched_root) and dst_dir.is_dir():
                for dep_rel in sorted(
                    _scan_dir_model_rel_paths(
                        dst_dir,
                        cache_root=cache_root,
                        patched_root=patched_root,
                        cache_resolver=cache_resolver,
                        uri_rule=uri_rule,
                    )
                ):
                    if dep_rel not in seen:
                        seen.add(dep_rel)
                        queue.append(dep_rel)
                        total += 1
            emit_fuel_progress(
                f"[{idx}/{total}] Patched model: {rel}",
                kind="model_patch",
                done=idx,
                total=total,
            )
        except (FileNotFoundError, ValueError):
            continue
    return patched_count


__all__ = [
    "asset_ref_from_rel_path",
    "ensure_complete_source_model",
    "patch_fuel_model",
    "sync_world_models_to_patched",
]
