from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .protocol import LauncherProtocol


@dataclass(kw_only=True, frozen=True)
class PrepareFolderLauncher(LauncherProtocol):
    runtime_dirs: tuple[Path, ...] = ()
    next_launcher: LauncherProtocol

    def __call__(self):
        for directory in self.runtime_dirs:
            directory.mkdir(parents=True, exist_ok=True)

        return self.next_launcher()
