from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Protocol

from ..models import AttachmentSpec, VehicleSpec


class AttachmentApplierProtocol(Protocol):
    def __call__(
        self, *, model: ET.Element, vehicle: VehicleSpec, attachment: AttachmentSpec
    ) -> None: ...
