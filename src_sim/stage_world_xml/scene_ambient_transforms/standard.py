import xml.etree.ElementTree as ET
from dataclasses import dataclass

from s7dcls import TransformProtocol

from lib.xml_helpers import ensure_child, set_child_text

from .models import AmbientColor


@dataclass(kw_only=True, frozen=True)
class StandardSceneAmbientTransform(TransformProtocol[ET.Element]):
    ambient: AmbientColor

    def __call__(self, x: ET.Element) -> ET.Element:
        scene = ensure_child(x, "scene")
        set_child_text(
            scene,
            "ambient",
            f"{self.ambient.red} {self.ambient.green} {self.ambient.blue} {self.ambient.alpha}",
        )
        return x
