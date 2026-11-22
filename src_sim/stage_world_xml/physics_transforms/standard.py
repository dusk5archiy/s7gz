from dataclasses import dataclass

from s7dcls import TransformProtocol

from lib.xml_helpers import ET, set_child_text


@dataclass(kw_only=True, frozen=True)
class StandardPhysicsTransform(TransformProtocol[ET.Element]):
    engine_name: str
    engine_type: str
    max_step_size: float
    real_time_factor: float
    collision_detector: str

    def __call__(self, x: ET.Element) -> ET.Element:
        for existing in list(x.findall("physics")):
            x.remove(existing)

        physics = ET.Element(
            "physics", {"name": self.engine_name, "type": self.engine_type}
        )
        set_child_text(physics, "max_step_size", str(self.max_step_size))
        set_child_text(physics, "real_time_factor", str(self.real_time_factor))
        if self.engine_type == "dart" and self.collision_detector:
            dart = ET.SubElement(physics, "dart")
            set_child_text(dart, "collision_detector", self.collision_detector)
        x.insert(0, physics)
        return x
