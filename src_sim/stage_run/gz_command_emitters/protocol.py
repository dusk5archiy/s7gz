from __future__ import annotations

from lib.type_emitters.protocol import TypeEmitterProtocol
from src_common.subprocess_launchers.models import SubprocessCommand

GzCommandEmitterProtocol = TypeEmitterProtocol[SubprocessCommand]
