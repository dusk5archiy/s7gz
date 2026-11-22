from dataclasses import dataclass

from s7dcls import TransformProtocol

from lib.xml_helpers import ET, find_plugin


@dataclass(kw_only=True, frozen=True)
class StandardSystemPluginsTransform(TransformProtocol[ET.Element]):
    plugins: tuple[tuple[str, str], ...]

    def __call__(self, x: ET.Element) -> ET.Element:
        for filename, classname in reversed(self.plugins):
            if find_plugin(x, filename=filename, name=classname) is None:
                x.insert(
                    0, ET.Element("plugin", {"filename": filename, "name": classname})
                )
        return x
