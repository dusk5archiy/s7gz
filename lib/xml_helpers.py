import xml.etree.ElementTree as ET


def ensure_child(parent: ET.Element, tag: str) -> ET.Element:
    child = parent.find(tag)
    if child is None:
        child = ET.SubElement(parent, tag)
    return child


def set_child_text(parent: ET.Element, tag: str, value: str) -> ET.Element:
    child = ensure_child(parent, tag)
    child.text = value
    return child


def plugin_stem(filename: str) -> str:
    stem = filename.strip()
    stem = stem.removeprefix("lib")
    stem = stem.removesuffix(".so")
    return stem


def find_plugin(
    world: ET.Element, *, filename: str, name: str
) -> ET.Element | None:
    target_stem = plugin_stem(filename)
    for plugin in world.findall("plugin"):
        if (
            plugin_stem(plugin.get("filename", "")) == target_stem
            or plugin.get("name") == name
        ):
            return plugin
    return None
