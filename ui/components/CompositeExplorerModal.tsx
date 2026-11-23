"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeftIcon,
  ArrowUpIcon,
  ChevronRightIcon,
  FolderIcon,
  TrashIcon,
  XIcon,
} from "@/components/ActionIcons";
import {
  defaultNonNullValue,
  FieldInput,
  getCompositeDepth,
  matchUnionVariantIndex,
} from "@/components/FieldInput";
import { deepEqual } from "@/lib/settings-utils";
import type { DataclassFieldSchema, SettingsFieldSchema } from "@/lib/types";

type PathSegment = string | number;

interface CompositeExplorerModalProps {
  open: boolean;
  title: string;
  subtitle?: string;
  schema: SettingsFieldSchema;
  value: unknown;
  onApply: (nextValue: unknown) => void;
  onClose: () => void;
}

interface ResolvedNode {
  schema: SettingsFieldSchema;
  effectiveSchema: SettingsFieldSchema;
  value: unknown;
  unionVariants?: SettingsFieldSchema[];
  unionActiveIdx?: number;
}

function isFolderSchema(schema: SettingsFieldSchema): boolean {
  return getCompositeDepth(schema) >= 2;
}

function unwrapSchemaForValue(
  schema: SettingsFieldSchema,
  value: unknown,
): ResolvedNode {
  if (schema.type === "union" && Array.isArray(schema.variants) && schema.variants.length > 0) {
    const activeIdx = matchUnionVariantIndex(schema.variants, value);
    const activeVariant = schema.variants[activeIdx];
    return {
      schema,
      effectiveSchema: activeVariant,
      value,
      unionVariants: schema.variants,
      unionActiveIdx: activeIdx,
    };
  }
  return { schema, effectiveSchema: schema, value };
}

function getChildSchema(
  parentEffSchema: SettingsFieldSchema,
  segment: PathSegment,
): SettingsFieldSchema {
  if (parentEffSchema.type === "dataclass" && typeof segment === "string") {
    const field = (parentEffSchema.fields ?? []).find((f) => f.name === segment);
    return field?.schema ?? { type: "str" };
  }
  if (parentEffSchema.type === "dict") {
    return parentEffSchema.value ?? { type: "str" };
  }
  if (parentEffSchema.type === "array") {
    return parentEffSchema.items && !Array.isArray(parentEffSchema.items)
      ? parentEffSchema.items
      : { type: "str" };
  }
  if (parentEffSchema.type === "tuple" && Array.isArray(parentEffSchema.items) && typeof segment === "number") {
    return parentEffSchema.items[segment] ?? { type: "str" };
  }
  return { type: "str" };
}

function resolveAtPath(
  rootSchema: SettingsFieldSchema,
  rootValue: unknown,
  path: PathSegment[],
): ResolvedNode {
  let currSchema = rootSchema;
  let currValue = rootValue;
  for (const seg of path) {
    const unwrapped = unwrapSchemaForValue(currSchema, currValue);
    const eff = unwrapped.effectiveSchema;
    currSchema = getChildSchema(eff, seg);
    if (typeof seg === "number" && Array.isArray(currValue)) {
      currValue = currValue[seg];
    } else if (
      typeof seg === "string" &&
      typeof currValue === "object" &&
      currValue !== null &&
      !Array.isArray(currValue)
    ) {
      currValue = (currValue as Record<string, unknown>)[seg];
    } else {
      currValue = undefined;
    }
  }
  return unwrapSchemaForValue(currSchema, currValue);
}

function setValueAtPath(
  rootValue: unknown,
  path: PathSegment[],
  nextVal: unknown,
): unknown {
  if (path.length === 0) return nextVal;
  const [head, ...rest] = path;
  if (typeof head === "number") {
    const arr = Array.isArray(rootValue) ? [...rootValue] : [];
    arr[head] = setValueAtPath(arr[head], rest, nextVal);
    return arr;
  }
  const obj =
    typeof rootValue === "object" && rootValue !== null && !Array.isArray(rootValue)
      ? { ...(rootValue as Record<string, unknown>) }
      : {};
  obj[head] = setValueAtPath(obj[head], rest, nextVal);
  return obj;
}

function smartArrayItemLabel(item: unknown, index: number): string {
  if (typeof item === "object" && item !== null && !Array.isArray(item)) {
    const rec = item as Record<string, unknown>;
    const tag =
      (typeof rec.namespace === "string" && rec.namespace.trim()) ||
      (typeof rec.gz_model_name === "string" && rec.gz_model_name.trim()) ||
      (typeof rec.name === "string" && rec.name.trim()) ||
      (typeof rec.slot === "string" && rec.slot.trim()) ||
      (typeof rec.kind === "string" && rec.kind.trim());
    if (tag) return `[${index}] ${tag}`;
  }
  return `[${index}]`;
}

export function summarizeCompositeValue(
  schema: SettingsFieldSchema,
  value: unknown,
): string {
  if (value === null) return "null";
  if (value === undefined) return "unset";
  const { effectiveSchema } = unwrapSchemaForValue(schema, value);
  if (effectiveSchema.type === "dict") {
    const keys =
      typeof value === "object" && !Array.isArray(value)
        ? Object.keys(value as Record<string, unknown>)
        : [];
    if (keys.length === 0) return "empty dict";
    if (keys.length === 1) return `1 key · ${keys[0]}`;
    return `${keys.length} keys`;
  }
  if (effectiveSchema.type === "array") {
    const len = Array.isArray(value) ? value.length : 0;
    return len === 1 ? "1 item" : `${len} items`;
  }
  if (effectiveSchema.type === "tuple") {
    const len = Array.isArray(value) ? value.length : 0;
    return `tuple (${len})`;
  }
  if (effectiveSchema.type === "dataclass") {
    const rec =
      typeof value === "object" && !Array.isArray(value)
        ? (value as Record<string, unknown>)
        : {};
    const parts: string[] = [];
    if (typeof rec.kind === "string") parts.push(rec.kind);
    else if (effectiveSchema.name) parts.push(effectiveSchema.name);
    if (typeof rec.relative_path === "string" && rec.relative_path) {
      parts.push(rec.relative_path);
    } else if (typeof rec.path === "string" && rec.path) {
      parts.push(rec.path);
    } else if (Array.isArray(rec.vehicles)) {
      parts.push(`${rec.vehicles.length} vehicle(s)`);
    } else {
      parts.push(`${(effectiveSchema.fields ?? []).length} fields`);
    }
    return parts.join(" · ");
  }
  return String(value);
}

interface TreeEntry {
  segment: PathSegment;
  label: string;
  schema: SettingsFieldSchema;
  value: unknown;
}

function getFolderChildren(node: ResolvedNode): TreeEntry[] {
  const eff = node.effectiveSchema;
  const val = node.value;
  if (val === null || val === undefined) return [];

  const out: TreeEntry[] = [];
  if (eff.type === "dict" && typeof val === "object" && !Array.isArray(val)) {
    const valSchema = eff.value ?? { type: "str" };
    if (isFolderSchema(valSchema)) {
      for (const [k, v] of Object.entries(val as Record<string, unknown>)) {
        out.push({ segment: k, label: k || "(empty)", schema: valSchema, value: v });
      }
    }
  } else if (eff.type === "array" && Array.isArray(val)) {
    const itemSchema =
      eff.items && !Array.isArray(eff.items) ? eff.items : { type: "str" };
    if (isFolderSchema(itemSchema)) {
      val.forEach((item, idx) => {
        out.push({
          segment: idx,
          label: smartArrayItemLabel(item, idx),
          schema: itemSchema,
          value: item,
        });
      });
    }
  } else if (eff.type === "tuple" && Array.isArray(eff.items) && Array.isArray(val)) {
    eff.items.forEach((itemSchema, idx) => {
      if (isFolderSchema(itemSchema)) {
        out.push({
          segment: idx,
          label: `[${idx}]`,
          schema: itemSchema,
          value: val[idx],
        });
      }
    });
  } else if (eff.type === "dataclass" && typeof val === "object" && !Array.isArray(val)) {
    const rec = val as Record<string, unknown>;
    for (const f of eff.fields ?? []) {
      if (isFolderSchema(f.schema)) {
        out.push({
          segment: f.name,
          label: f.name,
          schema: f.schema,
          value: rec[f.name],
        });
      }
    }
  }
  return out;
}

function pathKey(path: PathSegment[]): string {
  return JSON.stringify(path);
}

function FolderTreeNode({
  label,
  nodeSchema,
  nodeValue,
  path,
  activePathKey,
  expandedKeys,
  onToggleExpand,
  onSelectPath,
  depth = 0,
}: {
  label: string;
  nodeSchema: SettingsFieldSchema;
  nodeValue: unknown;
  path: PathSegment[];
  activePathKey: string;
  expandedKeys: Set<string>;
  onToggleExpand: (key: string) => void;
  onSelectPath: (path: PathSegment[]) => void;
  depth?: number;
}) {
  const key = pathKey(path);
  const resolved = unwrapSchemaForValue(nodeSchema, nodeValue);
  const children = getFolderChildren(resolved);
  const hasChildren = children.length > 0;
  const isExpanded = expandedKeys.has(key);
  const isActive = key === activePathKey;

  return (
    <div>
      <div
        className={`flex items-center gap-1 rounded-md px-1.5 py-1 text-xs transition ${
          isActive
            ? "bg-zinc-900 font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
            : "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-900"
        }`}
        style={{ paddingLeft: `${depth * 12 + 6}px` }}
      >
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            if (hasChildren) onToggleExpand(key);
          }}
          className={`inline-flex h-4 w-4 shrink-0 items-center justify-center rounded ${
            hasChildren ? "opacity-75 hover:opacity-100" : "invisible"
          }`}
          aria-label="Toggle folder"
        >
          <ChevronRightIcon
            className={`h-3 w-3 transition-transform ${isExpanded ? "rotate-90" : ""}`}
          />
        </button>
        <button
          type="button"
          onClick={() => onSelectPath(path)}
          className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
        >
          <FolderIcon
            className={`h-3.5 w-3.5 shrink-0 ${
              isActive
                ? "text-amber-300 dark:text-amber-600"
                : "text-amber-500 dark:text-amber-400"
            }`}
          />
          <span className="truncate font-mono text-[11px]">{label}</span>
        </button>
      </div>
      {hasChildren && isExpanded && (
        <div>
          {children.map((child) => (
            <FolderTreeNode
              key={`${key}:${String(child.segment)}`}
              label={child.label}
              nodeSchema={child.schema}
              nodeValue={child.value}
              path={[...path, child.segment]}
              activePathKey={activePathKey}
              expandedKeys={expandedKeys}
              onToggleExpand={onToggleExpand}
              onSelectPath={onSelectPath}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function CompositeExplorerModal({
  open,
  title,
  subtitle,
  schema,
  value,
  onApply,
  onClose,
}: CompositeExplorerModalProps) {
  const [draft, setDraft] = useState<unknown>(() => structuredClone(value));
  const [path, setPath] = useState<PathSegment[]>([]);
  const [history, setHistory] = useState<PathSegment[][]>([]);
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(() => new Set(["[]"]));
  const [newDictKey, setNewDictKey] = useState("");
  const [renamingKey, setRenamingKey] = useState<{ oldKey: string; text: string } | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  const currentNode = useMemo(
    () => resolveAtPath(schema, draft, path),
    [schema, draft, path],
  );

  const isDirty = useMemo(() => !deepEqual(draft, value), [draft, value]);

  if (!open) return null;

  const navigateTo = (nextPath: PathSegment[], pushHistory = true) => {
    if (pushHistory && pathKey(nextPath) !== pathKey(path)) {
      setHistory((prev) => [...prev, path]);
    }
    setPath(nextPath);
    setRenamingKey(null);
    setNewDictKey("");
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      for (let i = 0; i <= nextPath.length; i += 1) {
        next.add(pathKey(nextPath.slice(0, i)));
      }
      return next;
    });
  };

  const handleBack = () => {
    if (history.length === 0) return;
    const prevPath = history[history.length - 1];
    setHistory((h) => h.slice(0, -1));
    navigateTo(prevPath, false);
  };

  const handleUp = () => {
    if (path.length === 0) return;
    navigateTo(path.slice(0, -1));
  };

  const updateCurrentValue = (nextVal: unknown) => {
    setDraft((prev: unknown) => setValueAtPath(prev, path, nextVal));
  };

  const updateChildValue = (segment: PathSegment, nextVal: unknown) => {
    setDraft((prev: unknown) => setValueAtPath(prev, [...path, segment], nextVal));
  };

  const eff = currentNode.effectiveSchema;
  const currVal = currentNode.value;
  const activeKey = pathKey(path);

  const breadcrumbs = path.map((seg, idx) => {
    const parentNode = resolveAtPath(schema, draft, path.slice(0, idx));
    let label = String(seg);
    if (typeof seg === "number" && Array.isArray(parentNode.value)) {
      label = smartArrayItemLabel(parentNode.value[seg], seg);
    }
    return { label, targetPath: path.slice(0, idx + 1) };
  });

  const handleAddDictEntry = () => {
    const dictObj =
      typeof currVal === "object" && currVal !== null && !Array.isArray(currVal)
        ? (currVal as Record<string, unknown>)
        : {};
    const valSchema = eff.value ?? { type: "str" };
    let key = newDictKey.trim();
    if (!key) {
      let n = Object.keys(dictObj).length + 1;
      while (`key_${n}` in dictObj) n += 1;
      key = `key_${n}`;
    }
    if (key in dictObj) return;
    updateCurrentValue({ ...dictObj, [key]: defaultNonNullValue(valSchema) });
    setNewDictKey("");
    if (isFolderSchema(valSchema)) {
      navigateTo([...path, key]);
    }
  };

  const handleCommitRename = (oldKey: string, rawNewKey: string) => {
    const nextKey = rawNewKey.trim();
    setRenamingKey(null);
    if (!nextKey || nextKey === oldKey) return;
    const dictObj =
      typeof currVal === "object" && currVal !== null && !Array.isArray(currVal)
        ? (currVal as Record<string, unknown>)
        : {};
    if (nextKey in dictObj) return;
    const nextDict: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(dictObj)) {
      nextDict[k === oldKey ? nextKey : k] = v;
    }
    updateCurrentValue(nextDict);
  };

  const handleDeleteDictKey = (targetKey: string) => {
    const dictObj =
      typeof currVal === "object" && currVal !== null && !Array.isArray(currVal)
        ? { ...(currVal as Record<string, unknown>) }
        : {};
    delete dictObj[targetKey];
    updateCurrentValue(dictObj);
  };

  const handleAddArrayItem = () => {
    const arr = Array.isArray(currVal) ? [...currVal] : [];
    const itemSchema =
      eff.items && !Array.isArray(eff.items) ? eff.items : { type: "str" };
    const nextIndex = arr.length;
    arr.push(defaultNonNullValue(itemSchema));
    updateCurrentValue(arr);
    if (isFolderSchema(itemSchema)) {
      navigateTo([...path, nextIndex]);
    }
  };

  const handleMoveArrayItem = (index: number, delta: -1 | 1) => {
    const arr = Array.isArray(currVal) ? [...currVal] : [];
    const target = index + delta;
    if (target < 0 || target >= arr.length) return;
    const tmp = arr[index];
    arr[index] = arr[target];
    arr[target] = tmp;
    updateCurrentValue(arr);
  };

  const handleDuplicateArrayItem = (index: number) => {
    const arr = Array.isArray(currVal) ? [...currVal] : [];
    arr.splice(index + 1, 0, structuredClone(arr[index]));
    updateCurrentValue(arr);
  };

  const handleDeleteArrayItem = (index: number) => {
    const arr = Array.isArray(currVal) ? currVal.filter((_, i) => i !== index) : [];
    updateCurrentValue(arr);
  };

  const renderDataclassFields = (
    fields: DataclassFieldSchema[],
    objVal: Record<string, unknown>,
  ) => {
    const folderFields = fields.filter((f) => isFolderSchema(f.schema));
    const leafFields = fields.filter((f) => !isFolderSchema(f.schema));

    return (
      <div className="space-y-4">
        {folderFields.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
              Nested Folders ({folderFields.length})
            </div>
            <div className="divide-y divide-zinc-100 rounded-lg border border-zinc-200 dark:divide-zinc-900 dark:border-zinc-800">
              {folderFields.map((f) => {
                const fVal = objVal[f.name];
                const isNull = f.schema.nullable && fVal === null;
                return (
                  <div
                    key={f.name}
                    onClick={() => {
                      if (!isNull) navigateTo([...path, f.name]);
                    }}
                    className={`flex items-center justify-between gap-3 px-3 py-2.5 text-xs transition ${
                      isNull
                        ? "bg-zinc-50/50 dark:bg-zinc-900/30"
                        : "cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
                    }`}
                  >
                    <div className="flex min-w-0 items-center gap-2.5">
                      <FolderIcon
                        className={`h-4 w-4 shrink-0 ${
                          isNull
                            ? "text-zinc-400"
                            : "text-amber-500 dark:text-amber-400"
                        }`}
                      />
                      <div className="min-w-0">
                        <div className="truncate font-mono text-xs font-semibold">
                          {f.name}
                        </div>
                        {f.description && (
                          <div className="truncate text-[11px] text-zinc-500">
                            {f.description}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <span className="rounded bg-zinc-100 px-2 py-0.5 font-mono text-[10px] text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                        {summarizeCompositeValue(f.schema, fVal)}
                      </span>
                      {isNull ? (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            updateChildValue(f.name, defaultNonNullValue(f.schema));
                            navigateTo([...path, f.name]);
                          }}
                          className="rounded border border-zinc-300 bg-white px-2 py-0.5 text-[11px] font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                        >
                          Set value
                        </button>
                      ) : (
                        <ChevronRightIcon className="h-4 w-4 text-zinc-400" />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {leafFields.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
              Properties ({leafFields.length})
            </div>
            <div className="divide-y divide-zinc-100 rounded-lg border border-zinc-200 dark:divide-zinc-900 dark:border-zinc-800">
              {leafFields.map((f) => (
                <div
                  key={f.name}
                  className="grid gap-2 px-3 py-2.5 sm:grid-cols-12 sm:items-start"
                >
                  <div className="min-w-0 pt-1 sm:col-span-4">
                    <div className="truncate font-mono text-xs font-medium">
                      {f.name}
                    </div>
                    {f.description && (
                      <div className="text-[11px] text-zinc-500">{f.description}</div>
                    )}
                  </div>
                  <div className="min-w-0 sm:col-span-8">
                    <FieldInput
                      envKey={`${title}-${activeKey}-${f.name}`}
                      schema={f.schema}
                      value={objVal[f.name]}
                      onChange={(nextFieldVal) => updateChildValue(f.name, nextFieldVal)}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        className="flex h-[84vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-950"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <FolderIcon className="h-4 w-4 shrink-0 text-amber-500" />
              <h2 className="truncate font-mono text-sm font-semibold">{title}</h2>
              {isDirty && (
                <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-800 dark:bg-blue-950 dark:text-blue-300">
                  modified
                </span>
              )}
            </div>
            {subtitle && (
              <p className="mt-0.5 truncate text-xs text-zinc-500">{subtitle}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowRawJson((v) => !v)}
              className={`rounded-md border px-2.5 py-1 text-xs font-medium transition ${
                showRawJson
                  ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
                  : "border-zinc-300 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
              }`}
            >
              {showRawJson ? "Explorer View" : "Branch JSON"}
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close explorer"
              className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-zinc-200 text-zinc-500 hover:bg-zinc-100 dark:border-zinc-800 dark:hover:bg-zinc-900"
            >
              <XIcon className="h-3.5 w-3.5" />
            </button>
          </div>
        </header>

        <div className="flex items-center gap-1.5 border-b border-zinc-200 bg-zinc-50/70 px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900/40">
          <button
            type="button"
            disabled={history.length === 0}
            onClick={handleBack}
            title="Back"
            className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            <ArrowLeftIcon className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            disabled={path.length === 0}
            onClick={handleUp}
            title="Up one level"
            className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            <ArrowUpIcon className="h-3.5 w-3.5" />
          </button>

          <nav
            aria-label="Breadcrumb"
            className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto rounded-md border border-zinc-200 bg-white px-2.5 py-1 font-mono text-xs dark:border-zinc-800 dark:bg-zinc-950"
          >
            <button
              type="button"
              onClick={() => navigateTo([])}
              className={`shrink-0 rounded px-1 py-0.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 ${
                path.length === 0 ? "font-semibold" : "text-zinc-500"
              }`}
            >
              {title}
            </button>
            {breadcrumbs.map((crumb, idx) => (
              <div key={idx} className="flex shrink-0 items-center gap-1">
                <ChevronRightIcon className="h-3 w-3 text-zinc-400" />
                <button
                  type="button"
                  onClick={() => navigateTo(crumb.targetPath)}
                  className={`max-w-[220px] truncate rounded px-1 py-0.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 ${
                    idx === breadcrumbs.length - 1 ? "font-semibold" : "text-zinc-500"
                  }`}
                  title={crumb.label}
                >
                  {crumb.label}
                </button>
              </div>
            ))}
          </nav>
        </div>

        <div className="flex min-h-0 flex-1">
          <aside className="hidden w-64 shrink-0 overflow-y-auto border-r border-zinc-200 bg-zinc-50/40 p-2 md:block dark:border-zinc-800 dark:bg-zinc-900/20">
            <div className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
              Structure Tree
            </div>
            <FolderTreeNode
              label={title}
              nodeSchema={schema}
              nodeValue={draft}
              path={[]}
              activePathKey={activeKey}
              expandedKeys={expandedKeys}
              onToggleExpand={(k) =>
                setExpandedKeys((prev) => {
                  const next = new Set(prev);
                  if (next.has(k)) next.delete(k);
                  else next.add(k);
                  return next;
                })
              }
              onSelectPath={(target) => navigateTo(target)}
            />
          </aside>

          <section className="min-w-0 flex-1 overflow-y-auto p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-zinc-200 bg-zinc-50/60 px-3 py-2.5 dark:border-zinc-800 dark:bg-zinc-900/40">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs font-semibold">
                    {eff.name ?? eff.type}
                  </span>
                  <span className="rounded bg-zinc-200/80 px-1.5 py-0.5 font-mono text-[10px] text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                    {summarizeCompositeValue(currentNode.schema, currVal)}
                  </span>
                </div>
                {eff.description && (
                  <p className="mt-0.5 text-[11px] text-zinc-500">{eff.description}</p>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {currentNode.unionVariants && currVal !== null && (
                  <select
                    value={String(currentNode.unionActiveIdx ?? 0)}
                    onChange={(e) => {
                      const idx = Number.parseInt(e.target.value, 10);
                      const nextVariant = currentNode.unionVariants?.[idx];
                      if (nextVariant) {
                        updateCurrentValue(defaultNonNullValue(nextVariant));
                      }
                    }}
                    className="rounded-md border border-zinc-300 bg-white px-2 py-1 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-900"
                  >
                    {currentNode.unionVariants.map((v, idx) => (
                      <option key={idx} value={String(idx)}>
                        {v.name ?? v.type}
                      </option>
                    ))}
                  </select>
                )}

                {currentNode.schema.nullable && (
                  <button
                    type="button"
                    onClick={() =>
                      updateCurrentValue(
                        currVal === null ? defaultNonNullValue(currentNode.schema) : null,
                      )
                    }
                    className="rounded-md border border-zinc-300 bg-white px-2.5 py-1 text-xs font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                  >
                    {currVal === null ? "Set value" : "Set null"}
                  </button>
                )}

                {eff.type === "array" && currVal !== null && (
                  <button
                    type="button"
                    onClick={handleAddArrayItem}
                    className="rounded-md bg-zinc-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
                  >
                    + Add item
                  </button>
                )}

                {eff.type === "dict" && currVal !== null && (
                  <div className="flex items-center gap-1.5">
                    <input
                      type="text"
                      value={newDictKey}
                      onChange={(e) => setNewDictKey(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          handleAddDictEntry();
                        }
                      }}
                      placeholder="New key..."
                      className="w-40 rounded-md border border-zinc-300 bg-white px-2 py-1 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-900"
                    />
                    <button
                      type="button"
                      onClick={handleAddDictEntry}
                      className="rounded-md bg-zinc-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
                    >
                      + Add key
                    </button>
                  </div>
                )}
              </div>
            </div>

            {showRawJson ? (
              <pre className="overflow-auto rounded-lg border border-zinc-200 bg-zinc-950 p-4 font-mono text-xs text-zinc-100 dark:border-zinc-800">
                {JSON.stringify(currVal, null, 2)}
              </pre>
            ) : currVal === null ? (
              <div className="rounded-lg border border-dashed border-zinc-300 p-8 text-center text-xs text-zinc-500 dark:border-zinc-700">
                This value is currently <code className="font-mono">null</code>. Click{" "}
                <strong>Set value</strong> above to initialize it.
              </div>
            ) : eff.type === "dict" ? (
              (() => {
                const dictObj =
                  typeof currVal === "object" && !Array.isArray(currVal)
                    ? (currVal as Record<string, unknown>)
                    : {};
                const entries = Object.entries(dictObj);
                const valSchema = eff.value ?? { type: "str" };
                const childIsFolder = isFolderSchema(valSchema);

                if (entries.length === 0) {
                  return (
                    <div className="rounded-lg border border-dashed border-zinc-300 p-8 text-center text-xs text-zinc-500 dark:border-zinc-700">
                      Empty dictionary. Add a key above to get started.
                    </div>
                  );
                }

                return (
                  <div className="divide-y divide-zinc-100 rounded-lg border border-zinc-200 dark:divide-zinc-900 dark:border-zinc-800">
                    {entries.map(([k, v]) => {
                      const isRenaming = renamingKey?.oldKey === k;
                      return (
                        <div
                          key={k}
                          onClick={() => {
                            if (childIsFolder && !isRenaming) navigateTo([...path, k]);
                          }}
                          className={`flex flex-wrap items-center justify-between gap-3 px-3 py-2.5 text-xs transition ${
                            childIsFolder && !isRenaming
                              ? "cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
                              : ""
                          }`}
                        >
                          <div className="flex min-w-0 flex-1 items-center gap-2.5">
                            {childIsFolder && (
                              <FolderIcon className="h-4 w-4 shrink-0 text-amber-500 dark:text-amber-400" />
                            )}
                            {isRenaming ? (
                              <input
                                type="text"
                                autoFocus
                                value={renamingKey.text}
                                onClick={(e) => e.stopPropagation()}
                                onChange={(e) =>
                                  setRenamingKey({ oldKey: k, text: e.target.value })
                                }
                                onBlur={() => handleCommitRename(k, renamingKey.text)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") {
                                    e.preventDefault();
                                    handleCommitRename(k, renamingKey.text);
                                  } else if (e.key === "Escape") {
                                    setRenamingKey(null);
                                  }
                                }}
                                className="w-64 rounded border border-amber-400 bg-white px-2 py-1 font-mono text-xs dark:bg-zinc-900"
                              />
                            ) : (
                              <span className="truncate font-mono text-xs font-semibold">
                                {k}
                              </span>
                            )}
                          </div>

                          {childIsFolder ? (
                            <div
                              className="flex shrink-0 items-center gap-2"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <span className="rounded bg-zinc-100 px-2 py-0.5 font-mono text-[10px] text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                                {summarizeCompositeValue(valSchema, v)}
                              </span>
                              <button
                                type="button"
                                onClick={() => setRenamingKey({ oldKey: k, text: k })}
                                className="rounded border border-zinc-300 px-2 py-0.5 text-[11px] hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
                              >
                                Rename
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeleteDictKey(k)}
                                aria-label="Delete key"
                                className="inline-flex h-6 w-6 items-center justify-center rounded border border-rose-300 text-rose-600 hover:bg-rose-50 dark:border-rose-900/60 dark:text-rose-400 dark:hover:bg-rose-950/40"
                              >
                                <TrashIcon className="h-3 w-3" />
                              </button>
                              <button
                                type="button"
                                onClick={() => navigateTo([...path, k])}
                                aria-label="Open folder"
                                className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
                              >
                                <ChevronRightIcon className="h-4 w-4" />
                              </button>
                            </div>
                          ) : (
                            <div className="flex min-w-[220px] flex-1 items-center gap-2">
                              <div className="min-w-0 flex-1">
                                <FieldInput
                                  envKey={`${title}-${activeKey}-${k}`}
                                  schema={valSchema}
                                  value={v}
                                  onChange={(nextVal) => updateChildValue(k, nextVal)}
                                />
                              </div>
                              <button
                                type="button"
                                onClick={() => handleDeleteDictKey(k)}
                                aria-label="Delete key"
                                className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded border border-rose-300 text-rose-600 hover:bg-rose-50 dark:border-rose-900/60 dark:text-rose-400 dark:hover:bg-rose-950/40"
                              >
                                <TrashIcon className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })()
            ) : eff.type === "array" ? (
              (() => {
                const arr = Array.isArray(currVal) ? currVal : [];
                const itemSchema =
                  eff.items && !Array.isArray(eff.items) ? eff.items : { type: "str" };
                const childIsFolder = isFolderSchema(itemSchema);

                if (arr.length === 0) {
                  return (
                    <div className="rounded-lg border border-dashed border-zinc-300 p-8 text-center text-xs text-zinc-500 dark:border-zinc-700">
                      Empty list. Click <strong>+ Add item</strong> above.
                    </div>
                  );
                }

                return (
                  <div className="divide-y divide-zinc-100 rounded-lg border border-zinc-200 dark:divide-zinc-900 dark:border-zinc-800">
                    {arr.map((item, idx) => (
                      <div
                        key={idx}
                        onClick={() => {
                          if (childIsFolder) navigateTo([...path, idx]);
                        }}
                        className={`flex flex-wrap items-center justify-between gap-3 px-3 py-2.5 text-xs transition ${
                          childIsFolder
                            ? "cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
                            : ""
                        }`}
                      >
                        <div className="flex min-w-0 items-center gap-2.5">
                          {childIsFolder && (
                            <FolderIcon className="h-4 w-4 shrink-0 text-amber-500 dark:text-amber-400" />
                          )}
                          <span className="truncate font-mono text-xs font-semibold">
                            {smartArrayItemLabel(item, idx)}
                          </span>
                        </div>

                        {childIsFolder ? (
                          <div
                            className="flex shrink-0 items-center gap-1.5"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <span className="rounded bg-zinc-100 px-2 py-0.5 font-mono text-[10px] text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                              {summarizeCompositeValue(itemSchema, item)}
                            </span>
                            <button
                              type="button"
                              disabled={idx === 0}
                              onClick={() => handleMoveArrayItem(idx, -1)}
                              title="Move up"
                              className="rounded border border-zinc-300 px-1.5 py-0.5 text-[11px] hover:bg-zinc-100 disabled:opacity-35 dark:border-zinc-700 dark:hover:bg-zinc-800"
                            >
                              ↑
                            </button>
                            <button
                              type="button"
                              disabled={idx === arr.length - 1}
                              onClick={() => handleMoveArrayItem(idx, 1)}
                              title="Move down"
                              className="rounded border border-zinc-300 px-1.5 py-0.5 text-[11px] hover:bg-zinc-100 disabled:opacity-35 dark:border-zinc-700 dark:hover:bg-zinc-800"
                            >
                              ↓
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDuplicateArrayItem(idx)}
                              title="Duplicate"
                              className="rounded border border-zinc-300 px-1.5 py-0.5 text-[11px] hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
                            >
                              Copy
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteArrayItem(idx)}
                              aria-label="Delete item"
                              className="inline-flex h-6 w-6 items-center justify-center rounded border border-rose-300 text-rose-600 hover:bg-rose-50 dark:border-rose-900/60 dark:text-rose-400 dark:hover:bg-rose-950/40"
                            >
                              <TrashIcon className="h-3 w-3" />
                            </button>
                            <button
                              type="button"
                              onClick={() => navigateTo([...path, idx])}
                              aria-label="Open item"
                              className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
                            >
                              <ChevronRightIcon className="h-4 w-4" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex min-w-[220px] flex-1 items-center gap-2">
                            <div className="min-w-0 flex-1">
                              <FieldInput
                                envKey={`${title}-${activeKey}-${idx}`}
                                schema={itemSchema}
                                value={item}
                                onChange={(nextVal) => updateChildValue(idx, nextVal)}
                              />
                            </div>
                            <button
                              type="button"
                              onClick={() => handleDeleteArrayItem(idx)}
                              aria-label="Delete item"
                              className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded border border-rose-300 text-rose-600 hover:bg-rose-50 dark:border-rose-900/60 dark:text-rose-400 dark:hover:bg-rose-950/40"
                            >
                              <TrashIcon className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                );
              })()
            ) : eff.type === "tuple" && Array.isArray(eff.items) ? (
              <div className="divide-y divide-zinc-100 rounded-lg border border-zinc-200 dark:divide-zinc-900 dark:border-zinc-800">
                {eff.items.map((itemSchema, idx) => {
                  const arr = Array.isArray(currVal) ? currVal : [];
                  const itemVal = idx < arr.length ? arr[idx] : defaultNonNullValue(itemSchema);
                  const childIsFolder = isFolderSchema(itemSchema);
                  return (
                    <div
                      key={idx}
                      onClick={() => {
                        if (childIsFolder) navigateTo([...path, idx]);
                      }}
                      className={`grid gap-2 px-3 py-2.5 sm:grid-cols-12 sm:items-center ${
                        childIsFolder
                          ? "cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
                          : ""
                      }`}
                    >
                      <div className="flex items-center gap-2 sm:col-span-3">
                        {childIsFolder && <FolderIcon className="h-4 w-4 text-amber-500" />}
                        <span className="font-mono text-xs font-medium">[{idx}]</span>
                      </div>
                      <div className="sm:col-span-9">
                        {childIsFolder ? (
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-mono text-xs text-zinc-500">
                              {summarizeCompositeValue(itemSchema, itemVal)}
                            </span>
                            <ChevronRightIcon className="h-4 w-4 text-zinc-400" />
                          </div>
                        ) : (
                          <FieldInput
                            envKey={`${title}-${activeKey}-t${idx}`}
                            schema={itemSchema}
                            value={itemVal}
                            onChange={(nextVal) => updateChildValue(idx, nextVal)}
                          />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : eff.type === "dataclass" ? (
              renderDataclassFields(
                eff.fields ?? [],
                typeof currVal === "object" && currVal !== null && !Array.isArray(currVal)
                  ? (currVal as Record<string, unknown>)
                  : {},
              )
            ) : (
              <FieldInput
                envKey={`${title}-${activeKey}`}
                schema={eff}
                value={currVal}
                onChange={(nextVal) => updateCurrentValue(nextVal)}
              />
            )}
          </section>
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <span className="text-xs text-zinc-500">
            {isDirty
              ? "Changes will be staged to Settings draft when you click Apply."
              : "No changes made in this session."}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                onApply(draft);
                onClose();
              }}
              className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              Apply
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
