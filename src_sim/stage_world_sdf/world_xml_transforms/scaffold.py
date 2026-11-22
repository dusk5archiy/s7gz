from collections.abc import Sequence
from dataclasses import dataclass

from lib.type_emitters.protocol import TransformProtocol
from lib.xml_helpers import ET


@dataclass(kw_only=True, frozen=True)
class SequentialXmlTransform(TransformProtocol[ET.Element]):
    transforms: Sequence[TransformProtocol[ET.Element]] = ()

    def __call__(self, x):
        for transform in self.transforms:
            x = transform(x)

        return x
