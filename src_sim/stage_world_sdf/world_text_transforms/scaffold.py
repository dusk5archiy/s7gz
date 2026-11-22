import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from s7dcls import TransformProtocol


@dataclass(kw_only=True, frozen=True)
class ScaffoldWorldTextTransform(TransformProtocol[str]):
    world_transform: TransformProtocol[ET.Element] | None = None

    def __call__(self, text: str) -> str:
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        root = ET.fromstring(text)
        world = root.find("world")

        if world is None:
            raise ValueError({"world": None})

        if self.world_transform is not None:
            world = self.world_transform(world)

        ET.indent(root, space="  ")
        return '<?xml version="1.0" ?>\n' + ET.tostring(root, encoding="unicode") + "\n"
