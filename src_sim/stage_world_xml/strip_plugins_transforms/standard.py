from dataclasses import dataclass

from s7dcls import TransformProtocol

from lib.xml_helpers import ET, plugin_stem


@dataclass(kw_only=True, frozen=True)
class StandardStripPluginsTransform(TransformProtocol[ET.Element]):
    filename: str

    def __call__(self, x: ET.Element) -> ET.Element:
        target_stem = plugin_stem(self.filename)
        for plugin in list(x.findall("plugin")):
            raw_name = plugin.get("filename", "")
            if raw_name == self.filename or plugin_stem(raw_name) == target_stem:
                x.remove(plugin)
        return x
