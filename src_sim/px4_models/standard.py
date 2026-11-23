from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from s7dcls import FunctionProtocol


@dataclass(kw_only=True, frozen=True)
class GitSparsePx4ModelDownloader(FunctionProtocol[str, Path]):
    cache_dir: Path
    repo_url: str
    ref: str = "main"

    def _run_git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.cache_dir), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def __call__(self, x: str) -> Path:
        if not (self.cache_dir / ".git").is_dir():
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._run_git("init")
            self._run_git("remote", "add", "origin", self.repo_url)
            self._run_git("sparse-checkout", "init", "--cone")

        self._run_git("sparse-checkout", "add", f"models/{x}")
        self._run_git("fetch", "--depth", "1", "origin", self.ref)
        self._run_git("checkout", "-f", "FETCH_HEAD")

        model_dir = self.cache_dir / "models" / x
        if not model_dir.is_dir():
            raise FileNotFoundError(
                f"PX4 model {x!r} not found in {self.repo_url}@{self.ref}"
            )
        return model_dir
