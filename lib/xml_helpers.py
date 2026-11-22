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
