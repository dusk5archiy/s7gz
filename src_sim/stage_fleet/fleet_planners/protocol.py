from __future__ import annotations

from typing import Protocol

from ..models import FleetMember


class FleetPlannerProtocol(Protocol):
    def __call__(self) -> tuple[FleetMember, ...]: ...
