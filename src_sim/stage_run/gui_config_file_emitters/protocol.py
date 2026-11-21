from __future__ import annotations

from pathlib import Path

from lib.type_emitters.protocol import TypeEmitterProtocol

GuiConfigFileEmitterProtocol = TypeEmitterProtocol[Path | None]
