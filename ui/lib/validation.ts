import type { VehicleSpec } from "@/lib/types";

const NAMESPACE_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;

export interface VehicleFieldErrors {
  airframe?: string;
  namespace?: string;
}

export interface RosterValidationResult {
  errors: string[];
  byIndex: Record<number, VehicleFieldErrors>;
}

export function validateVehiclesRoster(vehicles: VehicleSpec[]): RosterValidationResult {
  const errors: string[] = [];
  const byIndex: Record<number, VehicleFieldErrors> = {};
  const seenNs = new Map<string, number>();

  vehicles.forEach((v, idx) => {
    const num = idx + 1;
    const fErr: VehicleFieldErrors = {};

    const af = v.airframe;
    if (!af) {
      fErr.airframe = "Airframe model SDF is required";
      errors.push(`Vehicle #${num}: airframe is required`);
    } else if (af.kind === "catalog") {
      const rel = (af.relative_path ?? "").trim();
      if (!rel) {
        fErr.airframe = "Catalog relative_path is required";
        errors.push(`Vehicle #${num}: catalog airframe relative_path is required`);
      } else if (rel.includes("\\") || rel.split("/").includes("..") || rel.startsWith("/")) {
        fErr.airframe = "Invalid catalog relative path";
        errors.push(`Vehicle #${num}: invalid catalog airframe '${rel}'`);
      } else if (!rel.toLowerCase().endsWith(".sdf")) {
        fErr.airframe = "Airframe path must end with .sdf";
        errors.push(`Vehicle #${num}: airframe must point to a .sdf file ('${rel}')`);
      }
    } else {
      const raw = (af.path ?? "").trim();
      if (!raw) {
        fErr.airframe = "Airframe path is required";
        errors.push(`Vehicle #${num}: airframe path is required`);
      } else if (raw.includes("\\")) {
        fErr.airframe = "Invalid path";
        errors.push(`Vehicle #${num}: invalid airframe path '${raw}'`);
      } else if (!raw.toLowerCase().endsWith(".sdf")) {
        fErr.airframe = "Airframe path must end with .sdf";
        errors.push(`Vehicle #${num}: airframe must point to a .sdf file ('${raw}')`);
      }
    }

    const ns = (v.namespace ?? "").trim();
    if (!ns) {
      fErr.namespace = "Namespace is required";
      errors.push(`Vehicle #${num}: namespace is required`);
    } else if (!NAMESPACE_RE.test(ns)) {
      fErr.namespace = "Use letters, digits, _ (start with letter or _)";
      errors.push(`Vehicle #${num}: invalid namespace '${ns}'`);
    } else if (seenNs.has(ns)) {
      const prev = seenNs.get(ns)!;
      fErr.namespace = `Duplicate of #${prev}`;
      errors.push(`Vehicle #${num}: duplicate namespace '${ns}'`);
    } else {
      seenNs.set(ns, num);
    }

    if (fErr.airframe || fErr.namespace) {
      byIndex[idx] = fErr;
    }
  });

  return { errors, byIndex };
}

export function validateFuelInput(name: string, url: string): string | null {
  const n = name.trim();
  const u = url.trim();
  if (!n && !u) {
    return "Please enter a name (owner/name) or a Fuel URL.";
  }
  if (u) {
    try {
      const parsed = new URL(u);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        return "Fuel URL must start with http:// or https://";
      }
    } catch {
      return "Invalid Fuel URL syntax.";
    }
  }
  if (n && (n.includes("\\") || n.includes("..") || n.startsWith("/"))) {
    return "Invalid asset name (cannot contain '\\', '..' or leading '/').";
  }
  return null;
}
