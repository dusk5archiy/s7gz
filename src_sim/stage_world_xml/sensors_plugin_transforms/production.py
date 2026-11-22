from dataclasses import dataclass, field

from s7dcls import TransformProtocol

from lib.xml_helpers import ET

from .settings import Settings
from .standard import StandardSensorsPluginTransform


@dataclass(kw_only=True, frozen=True)
class ProductionSensorsPluginTransform(TransformProtocol[ET.Element]):
    settings: Settings = field(default_factory=Settings.build)

    def __call__(self, x: ET.Element) -> ET.Element:
        if not self.settings.enabled:
            return x

        return StandardSensorsPluginTransform(
            render_engine=self.settings.render_engine
        )(x)
