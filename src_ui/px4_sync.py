from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from src_sim.px4_models.settings import Settings as Px4ModelsSettings
from src_sim.settings.resource import ResourceSettings


def _sync_tree_entries(src_dir: Path, dst_dir: Path, *, only_sdf_files: bool = False) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    if not src_dir.is_dir():
        return
    expected_names: set[str] = set()
    for entry in src_dir.iterdir():
        if entry.name.startswith("."):
            continue
        if only_sdf_files and (not entry.is_file() or entry.suffix.lower() != ".sdf"):
            continue
        expected_names.add(entry.name)
        target = dst_dir / entry.name
        if entry.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(entry, target)
        elif entry.is_file():
            shutil.copy2(entry, target)
    for existing in list(dst_dir.iterdir()):
        if existing.name not in expected_names:
            if existing.is_dir():
                shutil.rmtree(existing)
            else:
                existing.unlink()


def sync_px4_gazebo_repo(resource: ResourceSettings) -> None:
    """Sync PX4-gazebo-models git cache into source_models/px4 and source_worlds/px4."""
    px4_settings = Px4ModelsSettings.build()
    repo_dir = (resource.cache_dir / "px4_gazebo_models").resolve()

    def _git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo_dir), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    if not (repo_dir / ".git").is_dir():
        repo_dir.mkdir(parents=True, exist_ok=True)
        _git("init")
        _git("remote", "add", "origin", px4_settings.repo_url)
        _git("sparse-checkout", "init", "--cone")

    _git("sparse-checkout", "set", "models", "worlds")
    _git("fetch", "--depth", "1", "origin", px4_settings.ref)
    _git("checkout", "-f", "FETCH_HEAD")

    _sync_tree_entries(repo_dir / "models", resource.source_models_of("px4"))
    _sync_tree_entries(
        repo_dir / "worlds",
        resource.source_worlds_of("px4"),
        only_sdf_files=True,
    )
