from dataclasses import dataclass, field

from s7dcls import TransformProtocol

from lib.xml_helpers import ET

from .settings import Settings
from .standard import StandardSystemPluginsTransform


@dataclass(kw_only=True, frozen=True)
class ProductionSystemPluginsTransform(TransformProtocol[ET.Element]):
    settings: Settings = field(default_factory=Settings.build)

    def __call__(self, x: ET.Element) -> ET.Element:
        if not self.settings.enabled:
            return x

        return StandardSystemPluginsTransform(plugins=self.settings.plugins)(x)
