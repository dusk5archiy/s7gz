import type { AssetRef } from "@/lib/types";

export function assetRefToKey(ref: AssetRef | null | undefined): string | null {
  if (!ref) return null;
  if (ref.kind === "catalog") {
    const cleaned = ref.relative_path.trim().replace(/^\/+/, "");
    return cleaned ? `catalog:${cleaned}` : null;
  }
  const cleaned = ref.path.trim();
  return cleaned ? `path:${cleaned}` : null;
}

export function assetRefsEqual(
  a: AssetRef | null | undefined,
  b: AssetRef | null | undefined,
): boolean {
  if (!a && !b) return true;
  if (!a || !b) return false;
  if (a.kind !== b.kind) return false;
  if (a.kind === "catalog" && b.kind === "catalog") {
    return a.relative_path === b.relative_path;
  }
  if (a.kind === "path" && b.kind === "path") {
    return a.path === b.path;
  }
  return false;
}

export function formatAssetRef(ref: AssetRef | null | undefined): string {
  if (!ref) return "";
  return ref.kind === "catalog" ? ref.relative_path : ref.path;
}
