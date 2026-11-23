from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Protocol

from ..models import VehicleSpec


class AirframeBuilderProtocol(Protocol):
    def __call__(self, *, vehicle: VehicleSpec) -> ET.Element: ...
