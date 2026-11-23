from __future__ import annotations

from dataclasses import dataclass

from src_sim.settings.asset_ref import AssetRef

ScalarParam = str | int | float | bool


@dataclass(kw_only=True, frozen=True)
class BodyPose:
    """Local pose in Gazebo FLU (forward, left, up) coordinates."""

    forward_m: float = 0.0
    left_m: float = 0.0
    up_m: float = 0.0
    roll_rad: float = 0.0
    pitch_rad: float = 0.0
    yaw_rad: float = 0.0

    def to_sdf_pose_str(self) -> str:
        return (
            f"{self.forward_m:g} {self.left_m:g} {self.up_m:g} "
            f"{self.roll_rad:g} {self.pitch_rad:g} {self.yaw_rad:g}"
        )


@dataclass(kw_only=True, frozen=True)
class AttachmentSpec:
    slot: str
    kind: str
    pose_offset: BodyPose | None = None
    params: tuple[tuple[str, ScalarParam], ...] = ()


@dataclass(kw_only=True, frozen=True)
class DeviceSpec:
    name: str
    kind: str
    pose_offset: BodyPose | None = None
    params: tuple[tuple[str, ScalarParam], ...] = ()


@dataclass(kw_only=True, frozen=True)
class VehicleSpec:
    namespace: str
    airframe: AssetRef | None = None
    attachments: tuple[AttachmentSpec, ...] = ()
    devices: tuple[DeviceSpec, ...] = ()
