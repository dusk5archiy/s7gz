import type { SettingsField, SettingsFieldSchema } from "./types";

export function deepEqual(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) return true;
  if (typeof a !== typeof b || a === null || b === null) return false;
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((item, idx) => deepEqual(item, b[idx]));
  }
  if (typeof a === "object" && typeof b === "object") {
    const keysA = Object.keys(a as Record<string, unknown>);
    const keysB = Object.keys(b as Record<string, unknown>);
    if (keysA.length !== keysB.length) return false;
    return keysA.every((k) =>
      deepEqual(
        (a as Record<string, unknown>)[k],
        (b as Record<string, unknown>)[k],
      ),
    );
  }
  return false;
}

export function isFieldOverridden(field: SettingsField): boolean {
  if (field.is_ui_overridden !== undefined) return field.is_ui_overridden;
  if (field.has_default === false) return false;
  return !deepEqual(field.value, field.default);
}

export function formatSchemaSummary(schema: SettingsFieldSchema): string {
  const base = schema.nullable ? `${schema.type} | null` : schema.type;
  const bounds: string[] = [];
  if (schema.min !== undefined) bounds.push(`>= ${schema.min}`);
  if (schema.gt !== undefined) bounds.push(`> ${schema.gt}`);
  if (schema.max !== undefined) bounds.push(`<= ${schema.max}`);
  if (schema.lt !== undefined) bounds.push(`< ${schema.lt}`);
  if (bounds.length > 0) {
    return `${base} (${bounds.join(", ")})`;
  }
  return base;
}
