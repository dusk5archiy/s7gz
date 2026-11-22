import xml.etree.ElementTree as ET

from lib.type_emitters.protocol import TransformProtocol

WorldXmlTransformProtocol = TransformProtocol[ET.Element]
