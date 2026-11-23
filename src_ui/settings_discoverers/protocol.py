from __future__ import annotations

from s7dcls import EmitterProtocol

from ..models import SettingsGroup

SettingsDiscovererProtocol = EmitterProtocol[tuple[SettingsGroup, ...]]
