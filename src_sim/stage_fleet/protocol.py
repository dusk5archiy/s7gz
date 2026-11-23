from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Protocol

from .models import FleetMember


class FleetXmlPlacerProtocol(Protocol):
    def __call__(
        self, *, world: ET.Element, members: tuple[FleetMember, ...]
    ) -> ET.Element: ...
