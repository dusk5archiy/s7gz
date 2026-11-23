from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

DEFAULT_ENV_PREFIXES: tuple[str, ...] = ("__ARG__", "__HOST_", "__SIM__")


def load_env_from_script(
    script_path: Path,
    *,
    cwd: Path | None = None,
    prefixes: tuple[str, ...] = DEFAULT_ENV_PREFIXES,
) -> dict[str, str]:
    """Source a bash env script in a subshell and return matching env vars."""
    resolved = script_path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Env script not found: {resolved}")

    proc = subprocess.run(
        ["bash", "-c", f"set -a && source {shlex.quote(str(resolved))} && env -0"],
        cwd=cwd,
        capture_output=True,
        check=True,
    )
    loaded: dict[str, str] = {}
    for entry in proc.stdout.decode("utf-8", errors="replace").split("\0"):
        if "=" not in entry:
            continue
        key, val = entry.split("=", 1)
        if not prefixes or key.startswith(prefixes):
            loaded[key] = val
    return loaded


def apply_env_from_script(
    script_path: Path,
    *,
    cwd: Path | None = None,
    prefixes: tuple[str, ...] = DEFAULT_ENV_PREFIXES,
    override: bool = False,
) -> dict[str, str]:
    """Load env vars from a bash script into os.environ."""
    loaded = load_env_from_script(script_path, cwd=cwd, prefixes=prefixes)
    for key, val in loaded.items():
        if override:
            os.environ[key] = val
        else:
            os.environ.setdefault(key, val)
    return loaded


__all__ = ["DEFAULT_ENV_PREFIXES", "apply_env_from_script", "load_env_from_script"]
