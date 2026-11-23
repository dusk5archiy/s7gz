from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Protocol

from .models import VehicleSpec


class ModelPackageWriterProtocol(Protocol):
    def __call__(self, *, vehicle: VehicleSpec, sdf_root: ET.Element) -> Path: ...


class VehicleModelBuilderProtocol(Protocol):
    def __call__(self, *, vehicle: VehicleSpec) -> Path: ...
