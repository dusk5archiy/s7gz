import * as THREE from "three";
import type { GeoPose } from "@/lib/types";

/**
 * Canonical conversion between World-ENU (+X East, +Y North, +Z Up)
 * and Three.js native Y-up (+X East, +Y Up, -Z North).
 */
export function enuToThreePosition(
  eastM: number,
  northM: number,
  upM: number,
  target = new THREE.Vector3(),
): THREE.Vector3 {
  return target.set(eastM, upM, -northM);
}

export function threeToEnuPosition(vec: THREE.Vector3): {
  east_m: number;
  north_m: number;
  up_m: number;
} {
  return {
    east_m: Number(vec.x.toFixed(4)),
    north_m: Number((-vec.z).toFixed(4)),
    up_m: Number(vec.y.toFixed(4)),
  };
}

export function enuPoseToThreeQuaternion(
  pose: Pick<GeoPose, "roll_deg" | "pitch_deg" | "yaw_deg">,
  target = new THREE.Quaternion(),
): THREE.Quaternion {
  const deg2rad = Math.PI / 180;
  const enuEuler = new THREE.Euler(
    pose.roll_deg * deg2rad,
    pose.pitch_deg * deg2rad,
    pose.yaw_deg * deg2rad,
    "ZYX",
  );
  const qEnu = new THREE.Quaternion().setFromEuler(enuEuler);
  return target.set(qEnu.x, qEnu.z, -qEnu.y, qEnu.w);
}

export function threeQuaternionToEnuYawDeg(qThree: THREE.Quaternion): number {
  const qEnu = new THREE.Quaternion(qThree.x, -qThree.z, qThree.y, qThree.w);
  const eulerEnu = new THREE.Euler().setFromQuaternion(qEnu, "ZYX");
  return Number(((eulerEnu.z * 180) / Math.PI).toFixed(2));
}

export function applyEnuPoseToObject(
  obj: THREE.Object3D,
  pose: GeoPose,
): void {
  enuToThreePosition(pose.east_m, pose.north_m, pose.up_m, obj.position);
  enuPoseToThreeQuaternion(pose, obj.quaternion);
}
