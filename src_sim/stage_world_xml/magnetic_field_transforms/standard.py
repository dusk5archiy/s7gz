from dataclasses import dataclass

from s7dcls import TransformProtocol

from lib.xml_helpers import ET


@dataclass(kw_only=True, frozen=True)
class StandardMagneticFieldTransform(TransformProtocol[ET.Element]):
    magnetic_field: tuple[float, float, float]

    def __call__(self, x: ET.Element) -> ET.Element:
        if x.find("magnetic_field") is not None:
            return x

        mag = ET.Element("magnetic_field")
        mag.text = " ".join(str(v) for v in self.magnetic_field)
        sph_coords = x.find("spherical_coordinates")
        if sph_coords is not None:
            x.insert(list(x).index(sph_coords) + 1, mag)
        else:
            x.append(mag)
        return x
