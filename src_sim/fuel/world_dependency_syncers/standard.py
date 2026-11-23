from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from s7dcls import FunctionProtocol

from ..models import FuelAssetId, FuelAssetRef
from ..fuel_uris import FuelUriExtractor
from ..progress import run_with_current_context

FUEL_TEXT_EXTENSIONS: tuple[str, ...] = (".sdf", ".config", ".dae", ".material")


@dataclass(kw_only=True, frozen=True)
class ThreadedBatchAssetEnsurer:
    asset_ensurer: FunctionProtocol[FuelAssetRef, Path]
    max_workers: int = 4

    def __call__(self, *, refs: list[FuelAssetRef]) -> dict[FuelAssetId, Path]:
        if not refs:
            return {}
        worker_count = max(1, min(self.max_workers, len(refs)))
        resolved: dict[FuelAssetId, Path] = {}
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            future_to_id = {
                pool.submit(run_with_current_context, self.asset_ensurer, ref): ref.id
                for ref in refs
            }
            for future in as_completed(future_to_id):
                asset_id = future_to_id[future]
                resolved[asset_id] = future.result()
        return resolved


@dataclass(kw_only=True, frozen=True)
class BfsDependencyClosure(FunctionProtocol[str, dict[FuelAssetId, Path]]):
    batch_ensurer: ThreadedBatchAssetEnsurer
    ref_extractor: FuelUriExtractor
    text_extensions: tuple[str, ...] = FUEL_TEXT_EXTENSIONS

    def _scan_dir_refs(self, asset_dir: Path) -> list[FuelAssetRef]:
        refs: list[FuelAssetRef] = []
        for path in sorted(asset_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in self.text_extensions:
                refs.extend(
                    self.ref_extractor(
                        text=path.read_text(encoding="utf-8", errors="ignore")
                    )
                )
        return refs

    def __call__(self, x: str) -> dict[FuelAssetId, Path]:
        resolved: dict[FuelAssetId, Path] = {}
        frontier: dict[FuelAssetId, FuelAssetRef] = {
            ref.id: ref for ref in self.ref_extractor(text=x)
        }
        while frontier:
            batch = [frontier[asset_id] for asset_id in sorted(frontier)]
            frontier.clear()
            batch_dirs = self.batch_ensurer(refs=batch)
            resolved.update(batch_dirs)
            for version_dir in batch_dirs.values():
                for dep_ref in self._scan_dir_refs(version_dir):
                    if dep_ref.id not in resolved:
                        frontier.setdefault(dep_ref.id, dep_ref)
        return resolved
