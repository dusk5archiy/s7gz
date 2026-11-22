from __future__ import annotations

from pathlib import Path

from s7dcls import EmitterProtocol

GuiConfigFileEmitterProtocol = EmitterProtocol[Path | None]
