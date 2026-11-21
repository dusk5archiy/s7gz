from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src_common.subprocess_launchers.protocol import SubprocessLauncherProtocol

from .protocol import LauncherProtocol


@dataclass(kw_only=True, frozen=True)
class ScaffoldSimLauncher(LauncherProtocol):
    runtime_dirs: tuple[Path, ...]
    subprogress_launcher: SubprocessLauncherProtocol

    def __call__(self):
        for directory in self.runtime_dirs:
            directory.mkdir(parents=True, exist_ok=True)

        return self.subprogress_launcher()
