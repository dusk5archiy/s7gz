from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

from .models import GeoPose


def parse_sdf_pose(text: str) -> GeoPose:
    parts = [float(token) for token in text.split()]
    if len(parts) != 6:
        raise ValueError(f"Expected 6 pose numbers, got {len(parts)}: {text!r}")
    x, y, z, roll, pitch, yaw = parts
    return GeoPose(
        east_m=x,
        north_m=y,
        up_m=z,
        roll_deg=math.degrees(roll),
        pitch_deg=math.degrees(pitch),
        yaw_deg=math.degrees(yaw),
    )


def find_base_station_pose(world_root: ET.Element) -> GeoPose | None:
    """Find `<pose>` of `<include><name>base_station</name>` or `<model name='base_station'>`."""
    world_el = world_root if world_root.tag == "world" else world_root.find("world")
    search_root = world_el if world_el is not None else world_root

    for include_el in search_root.findall("include"):
        name_el = include_el.find("name")
        if name_el is not None and (name_el.text or "").strip() == "base_station":
            pose_el = include_el.find("pose")
            if pose_el is not None and (pose_el.text or "").strip():
                return parse_sdf_pose(pose_el.text.strip())

    for model_el in search_root.findall("model"):
        if model_el.attrib.get("name") == "base_station":
            pose_el = model_el.find("pose")
            if pose_el is not None and (pose_el.text or "").strip():
                return parse_sdf_pose(pose_el.text.strip())

    return None


def find_base_station_pose_from_file(sdf_path: Path) -> GeoPose | None:
    if not sdf_path.is_file():
        return None
    tree = ET.parse(sdf_path)
    return find_base_station_pose(tree.getroot())


def resolve_base_station_anchor(
    base_station: GeoPose | None,
    *,
    base_station_half_m: float = 1.5,
    gap_m: float = 3.0,
    depth_m: float = 0.0,
    front_east: float = 0.0,
    front_north: float = 1.0,
    offset_up_m: float = 0.3,
) -> GeoPose:
    if base_station is None:
        return GeoPose(up_m=offset_up_m)

    standoff_m = base_station_half_m + gap_m + depth_m
    yaw_rad = math.radians(base_station.yaw_deg)
    cos_y = math.cos(yaw_rad)
    sin_y = math.sin(yaw_rad)
    dir_east = front_east * cos_y - front_north * sin_y
    dir_north = front_east * sin_y + front_north * cos_y
    heading_deg = math.degrees(math.atan2(dir_north, dir_east))
    return GeoPose(
        east_m=base_station.east_m + dir_east * standoff_m,
        north_m=base_station.north_m + dir_north * standoff_m,
        up_m=base_station.up_m + offset_up_m,
        roll_deg=base_station.roll_deg,
        pitch_deg=base_station.pitch_deg,
        yaw_deg=heading_deg,
    )


__all__ = [
    "find_base_station_pose",
    "find_base_station_pose_from_file",
    "parse_sdf_pose",
    "resolve_base_station_anchor",
]
