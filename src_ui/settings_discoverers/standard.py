from __future__ import annotations

import importlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..models import SettingsGroup
from .protocol import SettingsDiscovererProtocol

_DEFAULT_SRC_SIM_DIR = Path(__file__).resolve().parent.parent.parent / "src_sim"


@lru_cache(maxsize=16)
def _discover_groups(
    root_dir: Path, package_prefix: str
) -> tuple[SettingsGroup, ...]:
    groups: list[SettingsGroup] = []
    for path in sorted(root_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if path.name != "settings.py" and "settings" not in path.parts:
            continue
        rel = path.relative_to(root_dir.parent)
        mod_name = ".".join(rel.with_suffix("").parts)
        mod = importlib.import_module(mod_name)
        prefix = getattr(mod, "PREFIX", None)
        cls = getattr(mod, "Settings", None)
        if isinstance(prefix, str) and isinstance(cls, type) and hasattr(cls, "build"):
            group_name = mod_name.removeprefix(package_prefix).removesuffix(".settings")
            groups.append(SettingsGroup(name=group_name, prefix=prefix, datacls=cls))
    return tuple(groups)


@dataclass(kw_only=True, frozen=True)
class StandardSettingsDiscoverer(SettingsDiscovererProtocol):
    root_dir: Path = _DEFAULT_SRC_SIM_DIR
    package_prefix: str = "src_sim."

    def __call__(self) -> tuple[SettingsGroup, ...]:
        return _discover_groups(self.root_dir, self.package_prefix)
