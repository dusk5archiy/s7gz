from __future__ import annotations

from pathlib import Path

from lib.type_emitters.protocol import EmitterProtocol

GuiConfigFileEmitterProtocol = EmitterProtocol[Path | None]
