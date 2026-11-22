import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from s7dcls import TransformProtocol

from .settings import Settings
from .standard import StandardSceneAmbientTransform


@dataclass(kw_only=True, frozen=True)
class ProductionSceneAmbientTransform(TransformProtocol[ET.Element]):
    settings: Settings = field(default_factory=Settings.build)

    def __call__(self, x):
        if not self.settings.enabled:
            return x

        return StandardSceneAmbientTransform(ambient=self.settings.ambient)(x)
