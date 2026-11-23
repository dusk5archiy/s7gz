from __future__ import annotations

from dataclasses import dataclass

from ..models import AttachmentSpec, VehicleSpec
from .protocol import AttachmentApplierProtocol


@dataclass(kw_only=True, frozen=True)
class AttachmentApplierRegistry(AttachmentApplierProtocol):
    appliers: dict[str, AttachmentApplierProtocol]

    def __call__(
        self, *, model, vehicle: VehicleSpec, attachment: AttachmentSpec
    ) -> None:
        applier = self.appliers.get(attachment.kind)
        if applier is None:
            raise KeyError(
                f"Unknown attachment kind {attachment.kind!r}; available: {sorted(self.appliers)}"
            )
        applier(model=model, vehicle=vehicle, attachment=attachment)
