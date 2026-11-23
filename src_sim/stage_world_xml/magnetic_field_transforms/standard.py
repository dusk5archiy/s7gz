from dataclasses import dataclass

from s7dcls import TransformProtocol

from lib.xml_helpers import ET

from .models import MagneticField


@dataclass(kw_only=True, frozen=True)
class StandardMagneticFieldTransform(TransformProtocol[ET.Element]):
    magnetic_field: MagneticField

    def __call__(self, x: ET.Element) -> ET.Element:
        if x.find("magnetic_field") is not None:
            return x

        mag = ET.Element("magnetic_field")
        mag.text = (
            f"{self.magnetic_field.x_east}"
            f" {self.magnetic_field.y_north}"
            f" {self.magnetic_field.z_up}"
        )
        sph_coords = x.find("spherical_coordinates")
        if sph_coords is not None:
            x.insert(list(x).index(sph_coords) + 1, mag)
        else:
            x.append(mag)
        return x
