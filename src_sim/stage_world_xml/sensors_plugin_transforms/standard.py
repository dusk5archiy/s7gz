from dataclasses import dataclass

from s7dcls import TransformProtocol

from lib.xml_helpers import ET, find_plugin, set_child_text


@dataclass(kw_only=True, frozen=True)
class StandardSensorsPluginTransform(TransformProtocol[ET.Element]):
    render_engine: str

    def __call__(self, x: ET.Element) -> ET.Element:
        filename = "gz-sim-sensors-system"
        classname = "gz::sim::systems::Sensors"
        plugin = find_plugin(x, filename=filename, name=classname)
        if plugin is None:
            plugin = ET.Element("plugin", {"filename": filename, "name": classname})
            x.insert(0, plugin)
        set_child_text(plugin, "render_engine", self.render_engine)
        return x
