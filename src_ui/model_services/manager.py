from __future__ import annotations

import os
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from src_sim.fuel.asset_ensurers.production import ProductionAssetEnsurer
from src_sim.fuel.cache_integrity import find_missing_asset_files
from src_sim.fuel.cache_resolvers.production import ProductionCacheResolver
from src_sim.fuel.models import FuelAssetRef
from src_sim.fuel.patched_models import asset_ref_from_rel_path, patch_fuel_model
from src_sim.fuel.uri_rules.production import ProductionFuelUriRule
from src_sim.fuel.world_asset_ensurers.standard import StandardFuelUrlParser
from src_sim.fuel.world_dependency_syncers.production import (
    ProductionWorldDependencySyncer,
)
from src_sim.fuel.world_url_emitters.settings import Settings as WorldUrlSettings
from src_sim.model_uris import write_lightweight_model_wrapper
from src_sim.settings.resource import ResourceSettings
from src_ui.providers import PROVIDERS, AssetProviderSpec, get_provider, provider_from_rel_path
from src_ui.px4_sync import sync_px4_gazebo_repo
from src_ui.thumbnail_utils import find_model_thumbnail_url
from src_ui.world_services.scene_graph import extract_model_visuals

ModelScope = Literal["source", "patched"]
_SDF_TAG_RE = re.compile(r"<sdf\b([^>]*)>", re.IGNORECASE)


def _dir_size_bytes(directory: Path) -> int:
    total = 0
    stack = [directory]
    while stack:
        curr = stack.pop()
        try:
            with os.scandir(curr) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
        except OSError:
            continue
    return total


def _fix_xml_namespaces(xml_text: str) -> str:
    try:
        ET.fromstring(xml_text)
        return xml_text
    except ET.ParseError:
        def _add_ns(match: re.Match[str]) -> str:
            attrs = match.group(1)
            extra = ""
            if "xmlns:gz=" not in attrs:
                extra += ' xmlns:gz="http://gazebosim.org/schema"'
            if "xmlns:ignition=" not in attrs:
                extra += ' xmlns:ignition="http://ignitionrobotics.org/schema"'
            return f"<sdf{attrs}{extra}>"

        patched = _SDF_TAG_RE.sub(_add_ns, xml_text, count=1)
        ET.fromstring(patched)
        return patched


def _scan_fuel_tree(
    provider_dir: Path,
    *,
    provider: str,
    scope: ModelScope,
    root_dir: Path,
    cwd_root: Path,
    source_models_dir: Path,
    patched_models_dir: Path,
) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    if not provider_dir.is_dir():
        return models
    cache_resolver = ProductionCacheResolver()
    uri_rule = ProductionFuelUriRule()
    for server_dir in sorted(provider_dir.iterdir(), key=lambda p: p.name.lower()):
        if not server_dir.is_dir() or server_dir.name.startswith("."):
            continue
        for owner_dir in sorted(server_dir.iterdir(), key=lambda p: p.name.lower()):
            models_root = owner_dir / "models"
            if not models_root.is_dir():
                continue
            for model_dir in sorted(models_root.iterdir(), key=lambda p: p.name.lower()):
                if not model_dir.is_dir():
                    continue
                for ver_dir in sorted(model_dir.iterdir(), key=lambda p: p.name.lower()):
                    if not ver_dir.is_dir():
                        continue
                    sdf_path = ver_dir / "model.sdf"
                    has_sdf = sdf_path.is_file()
                    stat = sdf_path.stat() if has_sdf else ver_dir.stat()
                    has_3d = False
                    if has_sdf:
                        try:
                            has_3d = bool(
                                extract_model_visuals(
                                    ver_dir,
                                    source_models_dir=source_models_dir,
                                    patched_models_dir=patched_models_dir,
                                    cache_resolver=cache_resolver,
                                    uri_rule=uri_rule,
                                )
                            )
                        except Exception:
                            has_3d = False
                    missing_files = find_missing_asset_files(
                        ver_dir,
                        check_dae_textures=False,
                        runtime_dir=source_models_dir.parent,
                    )
                    rel_path = ver_dir.relative_to(root_dir).as_posix()
                    display_path = ver_dir.relative_to(provider_dir).as_posix()
                    sdf_rel = (
                        sdf_path.resolve().relative_to(cwd_root).as_posix()
                        if has_sdf and sdf_path.resolve().is_relative_to(cwd_root)
                        else None
                    )
                    thumbnail_url = find_model_thumbnail_url(
                        ver_dir,
                        source_models_dir=source_models_dir,
                        patched_models_dir=patched_models_dir,
                        relative_path=rel_path,
                    )
                    models.append(
                        {
                            "provider": provider,
                            "scope": scope,
                            "relative_path": rel_path,
                            "display_path": display_path,
                            "sdf_rel_path": sdf_rel,
                            "server": server_dir.name,
                            "owner": owner_dir.name,
                            "name": model_dir.name,
                            "version": ver_dir.name,
                            "has_sdf": has_sdf,
                            "has_3d": has_3d,
                            "thumbnail_url": thumbnail_url,
                            "has_config": (ver_dir / "model.config").is_file(),
                            "is_patched": scope == "patched",
                            "missing_files": missing_files,
                            "size_bytes": _dir_size_bytes(ver_dir),
                            "modified_at": datetime.fromtimestamp(
                                stat.st_mtime, tz=UTC
                            ).isoformat(),
                        }
                    )
    return models


def _scan_flat_models(
    provider_dir: Path,
    *,
    provider: str,
    scope: ModelScope,
    root_dir: Path,
    cwd_root: Path,
    source_models_dir: Path,
    patched_models_dir: Path,
) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    if not provider_dir.is_dir():
        return models
    cache_resolver = ProductionCacheResolver()
    uri_rule = ProductionFuelUriRule()
    for entry in sorted(provider_dir.iterdir(), key=lambda p: p.name.lower()):
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
                        source_models_dir=source_models_dir,
                        patched_models_dir=patched_models_dir,
                        cache_resolver=cache_resolver,
                        uri_rule=uri_rule,
                    )
                )
            except Exception:
                has_3d = False
        rel_path = entry.relative_to(root_dir).as_posix()
        sdf_rel = (
            sdf_path.resolve().relative_to(cwd_root).as_posix()
            if has_sdf and sdf_path.resolve().is_relative_to(cwd_root)
            else None
        )
        thumbnail_url = find_model_thumbnail_url(
            entry,
            source_models_dir=source_models_dir,
            patched_models_dir=patched_models_dir,
            relative_path=rel_path,
        )
        models.append(
            {
                "provider": provider,
                "scope": scope,
                "relative_path": rel_path,
                "display_path": entry.name,
                "sdf_rel_path": sdf_rel,
                "name": entry.name,
                "has_sdf": has_sdf,
                "has_3d": has_3d,
                "thumbnail_url": thumbnail_url,
                "has_config": (entry / "model.config").is_file(),
                "is_patched": scope == "patched",
                "missing_files": [],
                "size_bytes": _dir_size_bytes(entry),
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
            }
        )
    return models


@dataclass(frozen=True)
class ModelManager:
    resource_settings: ResourceSettings
    providers: dict[str, AssetProviderSpec] = field(default_factory=lambda: dict(PROVIDERS))

    @classmethod
    def build(cls) -> ModelManager:
        return cls(resource_settings=ResourceSettings.build())

    @property
    def source_dir(self) -> Path:
        return self.resource_settings.source_models_dir.resolve()

    @property
    def patched_dir(self) -> Path:
        return self.resource_settings.patched_models_dir.resolve()

    def _scope_root(self, scope: ModelScope) -> Path:
        if scope == "patched":
            return self.patched_dir
        if scope == "source":
            return self.source_dir
        raise ValueError(f"Unknown model scope: {scope!r}")

    def _resolve_model_dir(
        self, relative_path: str, *, scope: ModelScope = "source"
    ) -> Path:
        cleaned = relative_path.strip().lstrip("/")
        if not cleaned or "\\" in cleaned or ".." in cleaned.split("/"):
            raise ValueError(f"Invalid model path: {relative_path!r}")
        root = self._scope_root(scope)
        target = (root / cleaned).resolve()
        if not target.is_relative_to(root) or not target.is_dir():
            raise FileNotFoundError(f"Model not found ({scope}): {relative_path!r}")
        return target

    def _scan_provider(
        self,
        spec: AssetProviderSpec,
        *,
        scope: ModelScope,
    ) -> list[dict[str, Any]]:
        root = self._scope_root(scope)
        prov_dir = root / spec.key
        cwd_root = Path.cwd().resolve()
        if spec.model_layout == "fuel_tree":
            return _scan_fuel_tree(
                prov_dir,
                provider=spec.key,
                scope=scope,
                root_dir=root,
                cwd_root=cwd_root,
                source_models_dir=self.source_dir,
                patched_models_dir=self.patched_dir,
            )
        return _scan_flat_models(
            prov_dir,
            provider=spec.key,
            scope=scope,
            root_dir=root,
            cwd_root=cwd_root,
            source_models_dir=self.source_dir,
            patched_models_dir=self.patched_dir,
        )

    def list_models(self) -> dict[str, Any]:
        cwd_root = Path.cwd().resolve()
        source_rel_root = (
            self.source_dir.relative_to(cwd_root).as_posix()
            if self.source_dir.is_relative_to(cwd_root)
            else str(self.source_dir)
        )
        patched_rel_root = (
            self.patched_dir.relative_to(cwd_root).as_posix()
            if self.patched_dir.is_relative_to(cwd_root)
            else str(self.patched_dir)
        )
        providers_payload: dict[str, dict[str, Any]] = {}
        for key, spec in self.providers.items():
            patched_models = self._scan_provider(spec, scope="patched")
            patched_rels = {m["relative_path"] for m in patched_models if m["has_sdf"]}
            source_models = self._scan_provider(spec, scope="source")
            for item in source_models:
                item["is_patched"] = item["relative_path"] in patched_rels
            providers_payload[key] = {
                "key": spec.key,
                "label": spec.label,
                "model_layout": spec.model_layout,
                "supports_download": spec.supports_download,
                "supports_sync": spec.supports_sync,
                "can_delete_source": spec.can_delete_source,
                "source_dir": str(self.source_dir / key),
                "source_rel_dir": f"{source_rel_root}/{key}",
                "patched_dir": str(self.patched_dir / key),
                "patched_rel_dir": f"{patched_rel_root}/{key}",
                "patched_models": patched_models,
                "source_models": source_models,
            }
        return {
            "source_dir": str(self.source_dir),
            "source_rel_dir": source_rel_root,
            "patched_dir": str(self.patched_dir),
            "patched_rel_dir": patched_rel_root,
            "providers": providers_payload,
        }

    def read_model_sdf(
        self, relative_path: str, *, scope: ModelScope = "source"
    ) -> dict[str, Any]:
        model_dir = self._resolve_model_dir(relative_path, scope=scope)
        sdf_path = model_dir / "model.sdf"
        if not sdf_path.is_file():
            raise FileNotFoundError(f"model.sdf not found for {relative_path!r}")
        content = sdf_path.read_text(encoding="utf-8", errors="replace")
        spec, _ = provider_from_rel_path(relative_path)
        name = model_dir.parent.name if spec.model_layout == "fuel_tree" else model_dir.name
        return {
            "scope": scope,
            "provider": spec.key,
            "relative_path": relative_path,
            "name": name,
            "size_bytes": sdf_path.stat().st_size,
            "content": content,
        }

    def delete_model(
        self, relative_path: str, *, scope: ModelScope = "source"
    ) -> dict[str, Any]:
        model_dir = self._resolve_model_dir(relative_path, scope=scope)
        shutil.rmtree(model_dir)
        return {"deleted": relative_path, "scope": scope, **self.list_models()}

    def _patch_px4_model(self, sub_rel: str) -> None:
        src_dir = self._resolve_model_dir(f"px4/{sub_rel}", scope="source")
        src_sdf = src_dir / "model.sdf"
        if not src_sdf.is_file():
            raise FileNotFoundError(f"model.sdf not found for px4/{sub_rel!r}")

        raw_text = src_sdf.read_text(encoding="utf-8", errors="replace")
        if "https://fuel." in raw_text or "http://fuel." in raw_text:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_sdf = Path(tmp) / "model.sdf"
                tmp_sdf.write_text(raw_text, encoding="utf-8")
                ProductionWorldDependencySyncer()(x=tmp_sdf)

        write_lightweight_model_wrapper(
            "px4",
            src_dir.name,
            resource=self.resource_settings,
        )

    def patch_model(self, relative_path: str) -> dict[str, Any]:
        spec, sub_rel = provider_from_rel_path(relative_path)
        repaired = False
        if spec.key == "fuel":
            repaired = patch_fuel_model(sub_rel, resource=self.resource_settings)
        elif spec.key == "px4":
            self._patch_px4_model(sub_rel)
        else:
            raise ValueError(f"Patching not implemented for provider {spec.key!r}")
        return {"patched": relative_path, "repaired": repaired, **self.list_models()}

    def redownload_model(
        self, relative_path: str, *, scope: ModelScope = "source"
    ) -> dict[str, Any]:
        spec, sub_rel = provider_from_rel_path(relative_path)
        if spec.key == "px4":
            sync_px4_gazebo_repo(self.resource_settings)
            patched_target = self.patched_dir / relative_path.strip().lstrip("/")
            if scope == "patched" or patched_target.is_dir():
                self._patch_px4_model(sub_rel)
            return {"redownloaded": relative_path, **self.list_models()}

        ref = asset_ref_from_rel_path(sub_rel)
        try:
            existing_source = self._resolve_model_dir(relative_path, scope="source")
            shutil.rmtree(existing_source)
        except FileNotFoundError:
            pass

        out_dir = ProductionAssetEnsurer()(ref)
        fuel_src_root = self.resource_settings.source_models_of("fuel").resolve()
        new_sub = out_dir.resolve().relative_to(fuel_src_root).as_posix()
        new_rel = f"fuel/{new_sub}"

        patched_exists = (self.patched_dir / relative_path.strip().lstrip("/")).is_dir()
        if scope == "patched" or patched_exists:
            patch_fuel_model(new_sub, resource=self.resource_settings)

        return {"redownloaded": new_rel, **self.list_models()}

    def download_model(
        self,
        *,
        model_url: str | None = None,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        ref: FuelAssetRef | None = None
        if model_url and model_url.strip():
            cleaned_url = model_url.strip()
            matches = ProductionFuelUriRule().find_all(text=cleaned_url)
            if matches:
                ref = matches[0].asset
            else:
                parsed = StandardFuelUrlParser()(cleaned_url)
                ref = FuelAssetRef(
                    server="fuel.gazebosim.org",
                    owner=parsed.owner,
                    asset_kind="models",
                    name=parsed.name,
                )
        elif model_name and model_name.strip():
            raw = model_name.strip()
            if "/" in raw:
                owner, name = (p.strip() for p in raw.split("/", 1))
            else:
                owner = WorldUrlSettings.build().default_owner
                name = raw
            ref = FuelAssetRef(
                server="fuel.gazebosim.org",
                owner=owner,
                asset_kind="models",
                name=name,
            )
        if ref is None:
            raise ValueError("Provide either model_url or model_name")

        out_dir = ProductionAssetEnsurer()(ref)
        fuel_src_root = self.resource_settings.source_models_of("fuel").resolve()
        rel = f"fuel/{out_dir.resolve().relative_to(fuel_src_root).as_posix()}"
        return {"downloaded": rel, **self.list_models()}

    def sync_provider(self, *, provider: str) -> dict[str, Any]:
        spec = get_provider(provider)
        if not spec.supports_sync:
            raise ValueError(f"Provider {provider!r} does not support sync")
        if spec.key == "px4":
            sync_px4_gazebo_repo(self.resource_settings)
        return self.list_models()


FuelModelManager = ModelManager
