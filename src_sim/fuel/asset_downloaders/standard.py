from __future__ import annotations

import json
import shutil
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from ..fs import atomic_path
from ..models import FuelAssetRef, FuelManifest
from ..progress import emit_fuel_progress
from .protocol import ManifestDownloaderProtocol, ManifestFetcherProtocol

_USER_AGENT = {"User-Agent": "s7gz-fuel/1.0"}


@dataclass(kw_only=True, frozen=True)
class StandardHttpEndpoint:
    scheme: str = "https"

    def asset_url(self, *, server: str, asset: FuelAssetRef) -> str:
        return (
            f"{self.scheme}://{server}/1.0/"
            f"{quote(asset.owner, safe='')}/{asset.asset_kind}/{quote(asset.name, safe='')}"
        )

    def manifest_url(self, *, server: str, asset: FuelAssetRef) -> str:
        return f"{self.asset_url(server=server, asset=asset)}/tip/files"

    def file_url(
        self, *, server: str, asset: FuelAssetRef, version: str, rel_path: str
    ) -> str:
        base = self.asset_url(server=server, asset=asset)
        return f"{base}/{quote(version, safe='')}/files/{quote(rel_path, safe='/')}"


@dataclass(kw_only=True, frozen=True)
class StandardManifestFetcher(ManifestFetcherProtocol):
    endpoint: StandardHttpEndpoint
    timeout_s: float

    @staticmethod
    def _parse_file_tree(tree: list[Any]) -> tuple[str, ...]:
        paths: list[str] = []
        stack = list(reversed(tree))
        while stack:
            node = stack.pop()
            if not isinstance(node, dict):
                continue
            children = node.get("children")
            if children is None:
                children = node.get("file_children")
            if isinstance(children, list):
                stack.extend(reversed(children))
                continue
            raw_path = node.get("path")
            if isinstance(raw_path, str):
                paths.append(raw_path.lstrip("/"))
        return tuple(paths)

    def __call__(self, *, server: str, asset: FuelAssetRef) -> FuelManifest:
        url = self.endpoint.manifest_url(server=server, asset=asset)
        req = urllib.request.Request(url, headers=_USER_AGENT)
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            payload = json.load(resp)
        if isinstance(payload, dict):
            raw_version = payload.get("version")
            tree = payload.get("file_tree", [])
        elif isinstance(payload, list):
            raw_version = 1
            tree = payload
        else:
            raise TypeError(
                f"Unexpected Fuel /tip/files JSON payload: {type(payload).__name__}"
            )
        if not isinstance(tree, list):
            raise TypeError("Invalid Fuel file_tree in response")
        version = "1" if raw_version is None else str(raw_version).strip()
        return FuelManifest(version=version, files=self._parse_file_tree(tree))


@dataclass(kw_only=True, frozen=True)
class StandardManifestDownloader(ManifestDownloaderProtocol):
    endpoint: StandardHttpEndpoint
    max_workers: int
    timeout_s: float

    def _download_one_file(
        self,
        *,
        server: str,
        asset: FuelAssetRef,
        version: str,
        rel_path: str,
        dest: Path,
    ) -> None:
        url = self.endpoint.file_url(
            server=server, asset=asset, version=version, rel_path=rel_path
        )
        req = urllib.request.Request(url, headers=_USER_AGENT)
        with (
            atomic_path(dest) as tmp_path,
            urllib.request.urlopen(req, timeout=self.timeout_s) as resp,
            tmp_path.open("wb") as out,
        ):
            shutil.copyfileobj(resp, out, length=64 * 1024)

    def __call__(
        self,
        *,
        server: str,
        asset: FuelAssetRef,
        manifest: FuelManifest,
        asset_root: Path,
    ) -> Path:
        version = manifest.version.strip()
        asset_root.mkdir(parents=True, exist_ok=True)
        version_dir = asset_root / version
        staging_dir = asset_root / f".tmp.{version}.{uuid4().hex[:8]}"
        staging_dir.mkdir(parents=True, exist_ok=True)
        total = len(manifest.files)
        emit_fuel_progress(
            f"Downloading {asset.owner}/{asset.asset_kind}/{asset.name} v{version} ({total} files)...",
            kind="asset_start",
            done=0,
            total=total,
        )
        try:
            worker_count = max(1, min(self.max_workers, len(manifest.files)))
            with ThreadPoolExecutor(max_workers=worker_count) as pool:
                future_to_rel = {
                    pool.submit(
                        self._download_one_file,
                        server=server,
                        asset=asset,
                        version=version,
                        rel_path=rel_path,
                        dest=staging_dir / rel_path,
                    ): rel_path
                    for rel_path in manifest.files
                }
                done = 0
                try:
                    for future in as_completed(future_to_rel):
                        future.result()
                        done += 1
                        rel_path = future_to_rel[future]
                        emit_fuel_progress(
                            f"[{done}/{total}] {asset.name}: {rel_path}",
                            kind="file",
                            done=done,
                            total=total,
                        )
                except Exception:
                    for future in future_to_rel:
                        future.cancel()
                    raise
            if version_dir.exists():
                shutil.rmtree(version_dir)
            staging_dir.replace(version_dir)
            return version_dir
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise
