from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Protocol

from ..models import DeviceSpec, VehicleSpec


class DeviceApplierProtocol(Protocol):
    def __call__(
        self, *, model: ET.Element, vehicle: VehicleSpec, device: DeviceSpec
    ) -> None: ...
