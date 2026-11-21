from dataclasses import dataclass
from pathlib import Path


@dataclass(kw_only=True, frozen=True)
class VolumeMount:
    source: Path | str
    target: Path | str
    mode: str | None = None

    def to_arg(self) -> str:
        base = f"{self.source}:{self.target}"
        return f"{base}:{self.mode}" if self.mode else base
