from __future__ import annotations

from typing import Protocol

from ..models import GeoPose


class FormationProtocol(Protocol):
    def poses(
        self,
        *,
        center: GeoPose,
        count: int,
    ) -> tuple[GeoPose, ...]: ...
