from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from s7dcls import FunctionProtocol


def _validate_model_name(name: str) -> str:
    cleaned = name.strip()
    if (
        not cleaned
        or cleaned in (".", "..")
        or "/" in cleaned
        or "\\" in cleaned
    ):
        raise ValueError(f"Invalid PX4 model name: {name!r}")
    return cleaned


@dataclass(kw_only=True, frozen=True)
class ScaffoldPx4ModelEnsurer(FunctionProtocol[str, Path]):
    cache_dir: Path
    downloader: FunctionProtocol[str, Path]

    def __call__(self, x: str) -> Path:
        model_name = _validate_model_name(x)
        model_dir = self.cache_dir / "models" / model_name
        if model_dir.is_dir() and any(model_dir.iterdir()):
            return model_dir
        return self.downloader(model_name)
