from dataclasses import dataclass, field

from s7dcls import TransformProtocol

from lib.xml_helpers import ET

from .settings import Settings
from .standard import StandardPhysicsTransform


@dataclass(kw_only=True, frozen=True)
class ProductionPhysicsTransform(TransformProtocol[ET.Element]):
    settings: Settings = field(default_factory=Settings.build)

    def __call__(self, x: ET.Element) -> ET.Element:
        if not self.settings.enabled:
            return x

        return StandardPhysicsTransform(
            engine_name=self.settings.engine_name,
            engine_type=self.settings.engine_type,
            max_step_size=self.settings.max_step_size,
            real_time_factor=self.settings.real_time_factor,
            collision_detector=self.settings.collision_detector,
        )(x)
