"use client";

import { useState } from "react";
import type { SettingsFieldSchema } from "@/lib/types";

interface FieldInputProps {
  envKey: string;
  schema: SettingsFieldSchema;
  value: unknown;
  onChange: (nextValue: unknown) => void;
}

export function getCompositeDepth(schema: SettingsFieldSchema): number {
  switch (schema.type) {
    case "dataclass": {
      const depths = (schema.fields ?? []).map((f) => getCompositeDepth(f.schema));
      return 1 + (depths.length > 0 ? Math.max(...depths) : 0);
    }
    case "dict":
      return 1 + getCompositeDepth(schema.value ?? { type: "str" });
    case "array": {
      const itemSchema =
        schema.items && !Array.isArray(schema.items) ? schema.items : { type: "str" };
      return 1 + getCompositeDepth(itemSchema);
    }
    case "tuple": {
      const items = Array.isArray(schema.items) ? schema.items : [];
      return 1 + (items.length > 0 ? Math.max(...items.map(getCompositeDepth)) : 0);
    }
    case "union": {
      const variants = schema.variants ?? [];
      return variants.length > 0 ? Math.max(...variants.map(getCompositeDepth)) : 0;
    }
    default:
      return 0;
  }
}

export function defaultNonNullValue(schema: SettingsFieldSchema): unknown {
  switch (schema.type) {
    case "bool":
      return false;
    case "int":
      return schema.min ?? 0;
    case "float":
      return schema.min ?? (schema.gt !== undefined ? schema.gt + 1.0 : 0);
    case "literal":
      return schema.choices?.[0] ?? "";
    case "union":
      return schema.variants?.[0] ? defaultNonNullValue(schema.variants[0]) : null;
    case "array":
      return [];
    case "tuple":
      return Array.isArray(schema.items)
        ? schema.items.map((item) => defaultNonNullValue(item))
        : [];
    case "dict":
      return {};
    case "dataclass": {
      const obj: Record<string, unknown> = {};
      for (const f of schema.fields ?? []) {
        obj[f.name] =
          f.default !== undefined
            ? structuredClone(f.default)
            : f.schema.nullable
              ? null
              : defaultNonNullValue(f.schema);
      }
      return obj;
    }
    case "str":
    case "path":
    default:
      return "";
  }
}

function computeSliderStep(min: number, max: number, isInt: boolean): number {
  if (isInt) return 1;
  const span = max - min;
  if (span <= 0) return 0.01;
  const raw = span / 100;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const niceNorm = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10;
  return Number((niceNorm * mag).toPrecision(6));
}

function roundToStep(value: number, step: number, isInt: boolean): number {
  if (isInt) return Math.round(value);
  const decimals = Math.max(0, Math.ceil(-Math.log10(step)));
  return Number(value.toFixed(decimals));
}

function NumberInput({
  schema,
  value,
  onChange,
}: {
  schema: SettingsFieldSchema;
  value: number;
  onChange: (next: number) => void;
}) {
  const isInt = schema.type === "int";
  const [rawText, setRawText] = useState(() => String(value));
  const [prevPropValue, setPrevPropValue] = useState(value);

  if (value !== prevPropValue) {
    setPrevPropValue(value);
    setRawText(String(value));
  }

  const hasBounds =
    schema.min !== undefined &&
    schema.max !== undefined &&
    schema.max > schema.min;

  const numberEl = (
    <input
      type="number"
      step={isInt ? 1 : "any"}
      min={schema.min}
      max={schema.max}
      value={rawText}
      onChange={(e) => {
        const nextText = e.target.value;
        setRawText(nextText);
        if (nextText.trim() === "") return;
        const parsed = isInt
          ? Number.parseInt(nextText, 10)
          : Number.parseFloat(nextText);
        if (Number.isFinite(parsed)) {
          onChange(parsed);
        }
      }}
      onBlur={() => {
        setRawText(String(value));
      }}
      className={`${hasBounds ? "w-24 shrink-0 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none" : "w-full"} rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 font-mono text-xs outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900`}
    />
  );

  if (!hasBounds) {
    return numberEl;
  }

  const minVal = schema.min as number;
  const maxVal = schema.max as number;
  const sliderStep = computeSliderStep(minVal, maxVal, isInt);
  const clamped = Math.min(maxVal, Math.max(minVal, value));

  return (
    <div className="flex items-center gap-3">
      {numberEl}
      <input
        type="range"
        min={minVal}
        max={maxVal}
        step={sliderStep}
        value={clamped}
        onChange={(e) => {
          const next = Number.parseFloat(e.target.value);
          if (Number.isFinite(next)) {
            onChange(roundToStep(next, sliderStep, isInt));
          }
        }}
        className="min-w-0 flex-1 cursor-pointer accent-zinc-900 dark:accent-zinc-100"
      />
    </div>
  );
}

function ArrayInput({
  envKey,
  itemSchema,
  value,
  onChange,
}: {
  envKey: string;
  itemSchema: SettingsFieldSchema;
  value: unknown[];
  onChange: (next: unknown[]) => void;
}) {
  return (
    <div className="space-y-2">
      {value.length === 0 && (
        <div className="rounded border border-dashed border-zinc-300 px-2.5 py-1.5 text-xs text-zinc-400 dark:border-zinc-700">
          Empty list
        </div>
      )}
      {value.map((item, index) => (
        <div key={index} className="flex items-start gap-1.5">
          <div className="min-w-0 flex-1">
            <FieldInput
              envKey={`${envKey}-${index}`}
              schema={itemSchema}
              value={item}
              onChange={(nextItem) => {
                const next = [...value];
                next[index] = nextItem;
                onChange(next);
              }}
            />
          </div>
          <button
            type="button"
            onClick={() => onChange(value.filter((_, i) => i !== index))}
            className="shrink-0 rounded border border-zinc-300 px-2 py-1.5 text-xs text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            Remove
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...value, defaultNonNullValue(itemSchema)])}
        className="rounded border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
      >
        + Add item
      </button>
    </div>
  );
}

function TupleInput({
  envKey,
  itemSchemas,
  value,
  onChange,
}: {
  envKey: string;
  itemSchemas: SettingsFieldSchema[];
  value: unknown[];
  onChange: (next: unknown[]) => void;
}) {
  const normalized = itemSchemas.map((s, idx) =>
    idx < value.length ? value[idx] : defaultNonNullValue(s),
  );

  return (
    <div className="grid gap-1.5 sm:grid-cols-2">
      {itemSchemas.map((itemSchema, idx) => (
        <div key={idx} className="min-w-0">
          <FieldInput
            envKey={`${envKey}-t${idx}`}
            schema={itemSchema}
            value={normalized[idx]}
            onChange={(nextItem) => {
              const next = [...normalized];
              next[idx] = nextItem;
              onChange(next);
            }}
          />
        </div>
      ))}
    </div>
  );
}

function DictInput({
  envKey,
  valueSchema,
  value,
  onChange,
}: {
  envKey: string;
  valueSchema: SettingsFieldSchema;
  value: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
}) {
  const entries = Object.entries(value);

  const commitEntries = (nextEntries: [string, unknown][]) => {
    const obj: Record<string, unknown> = {};
    for (const [k, v] of nextEntries) {
      obj[k] = v;
    }
    onChange(obj);
  };

  return (
    <div className="space-y-2 rounded-md border border-zinc-200 p-2.5 dark:border-zinc-800">
      {entries.length === 0 && (
        <div className="text-xs text-zinc-400">Empty dict</div>
      )}
      {entries.map(([k, v], index) => (
        <div key={index} className="flex items-start gap-1.5">
          <input
            type="text"
            value={k}
            placeholder="key"
            onChange={(e) => {
              const nextEntries = [...entries];
              nextEntries[index] = [e.target.value, v];
              commitEntries(nextEntries);
            }}
            className="w-32 shrink-0 rounded-md border border-zinc-300 bg-white px-2 py-1.5 font-mono text-xs outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <div className="min-w-0 flex-1">
            <FieldInput
              envKey={`${envKey}-d${index}`}
              schema={valueSchema}
              value={v}
              onChange={(nextVal) => {
                const nextEntries = [...entries];
                nextEntries[index] = [k, nextVal];
                commitEntries(nextEntries);
              }}
            />
          </div>
          <button
            type="button"
            onClick={() =>
              commitEntries(entries.filter((_, i) => i !== index))
            }
            className="shrink-0 rounded border border-zinc-300 px-2 py-1.5 text-xs text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            Remove
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => {
          let idx = entries.length + 1;
          while (`key_${idx}` in value) idx += 1;
          commitEntries([
            ...entries,
            [`key_${idx}`, defaultNonNullValue(valueSchema)],
          ]);
        }}
        className="rounded border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
      >
        + Add entry
      </button>
    </div>
  );
}

function DataclassInput({
  envKey,
  schema,
  value,
  onChange,
}: {
  envKey: string;
  schema: SettingsFieldSchema;
  value: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
}) {
  const fieldSchemas = schema.fields ?? [];

  return (
    <div className="space-y-2.5 rounded-md border border-zinc-200 p-3 dark:border-zinc-800">
      {schema.name && (
        <div className="space-y-0.5">
          <div className="font-mono text-[11px] font-medium text-zinc-500">
            {schema.name}
          </div>
          {schema.description && (
            <p className="whitespace-pre-line text-xs text-zinc-500 dark:text-zinc-400">
              {schema.description}
            </p>
          )}
        </div>
      )}
      {fieldSchemas.map((f) => (
        <div key={f.name} className="space-y-1">
          <div className="font-mono text-xs text-zinc-600 dark:text-zinc-400">
            {f.name}
          </div>
          {f.description && (
            <p className="whitespace-pre-line text-[11px] text-zinc-500 dark:text-zinc-400">
              {f.description}
            </p>
          )}
          <FieldInput
            envKey={`${envKey}-${f.name}`}
            schema={f.schema}
            value={value[f.name]}
            onChange={(nextFieldVal) =>
              onChange({ ...value, [f.name]: nextFieldVal })
            }
          />
        </div>
      ))}
    </div>
  );
}

export function matchUnionVariantIndex(
  variants: SettingsFieldSchema[],
  value: unknown,
): number {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    const obj = value as Record<string, unknown>;
    const idx = variants.findIndex((variant) => {
      if (variant.type !== "dataclass" || !variant.fields) return false;
      return variant.fields.every((f) => {
        if (f.schema.type === "literal" && Array.isArray(f.schema.choices)) {
          return f.schema.choices.includes(obj[f.name]);
        }
        return true;
      });
    });
    if (idx >= 0) return idx;
  }
  return 0;
}

function UnionInput({
  envKey,
  variants,
  value,
  onChange,
}: {
  envKey: string;
  variants: SettingsFieldSchema[];
  value: unknown;
  onChange: (next: unknown) => void;
}) {
  if (variants.length === 0) {
    return <span className="font-mono text-xs text-zinc-400">empty union</span>;
  }

  const activeIdx = matchUnionVariantIndex(variants, value);
  const activeVariant = variants[activeIdx];

  return (
    <div className="space-y-2">
      <select
        value={String(activeIdx)}
        onChange={(e) => {
          const nextIdx = Number.parseInt(e.target.value, 10);
          if (nextIdx >= 0 && nextIdx < variants.length) {
            onChange(defaultNonNullValue(variants[nextIdx]));
          }
        }}
        className="w-full rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 font-mono text-xs outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
      >
        {variants.map((variant, idx) => (
          <option key={idx} value={String(idx)}>
            {variant.name ?? variant.type}
          </option>
        ))}
      </select>
      <FieldInput
        envKey={`${envKey}-u${activeIdx}`}
        schema={activeVariant}
        value={value}
        onChange={onChange}
      />
    </div>
  );
}

export function FieldInput({
  envKey,
  schema,
  value,
  onChange,
}: FieldInputProps) {
  if (schema.nullable && value === null) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-md border border-dashed border-zinc-300 bg-zinc-50 px-2.5 py-1.5 dark:border-zinc-700 dark:bg-zinc-900/50">
        <span className="font-mono text-xs text-zinc-400">null</span>
        <button
          type="button"
          onClick={() => onChange(defaultNonNullValue(schema))}
          className="rounded border border-zinc-300 bg-white px-2 py-0.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
        >
          Set value
        </button>
      </div>
    );
  }

  let control: React.ReactNode;

  if (schema.type === "bool") {
    const checked = Boolean(value);
    control = (
      <label
        htmlFor={`field-${envKey}`}
        className="inline-flex cursor-pointer items-center gap-2.5 rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 text-xs dark:border-zinc-700 dark:bg-zinc-900"
      >
        <input
          id={`field-${envKey}`}
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="h-4 w-4 accent-zinc-900 dark:accent-zinc-100"
        />
        <span className="font-mono">{checked ? "true" : "false"}</span>
      </label>
    );
  } else if (schema.type === "literal" && Array.isArray(schema.choices)) {
    const choices = schema.choices;
    const selectedIndex = choices.findIndex(
      (choice) => JSON.stringify(choice) === JSON.stringify(value),
    );
    control = (
      <select
        value={selectedIndex >= 0 ? String(selectedIndex) : ""}
        onChange={(e) => {
          const idx = Number.parseInt(e.target.value, 10);
          if (idx >= 0 && idx < choices.length) {
            onChange(choices[idx]);
          }
        }}
        className="w-full rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 font-mono text-xs outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
      >
        {choices.map((choice, idx) => (
          <option key={idx} value={String(idx)}>
            {String(choice)}
          </option>
        ))}
      </select>
    );
  } else if (schema.type === "int" || schema.type === "float") {
    const numericValue = typeof value === "number" ? value : 0;
    control = (
      <NumberInput
        schema={schema}
        value={numericValue}
        onChange={(next) => onChange(next)}
      />
    );
  } else if (schema.type === "array") {
    const arrValue = Array.isArray(value) ? value : [];
    const itemSchema =
      schema.items && !Array.isArray(schema.items)
        ? schema.items
        : { type: "str" };
    control = (
      <ArrayInput
        envKey={envKey}
        itemSchema={itemSchema}
        value={arrValue}
        onChange={(next) => onChange(next)}
      />
    );
  } else if (schema.type === "tuple" && Array.isArray(schema.items)) {
    const tupleValue = Array.isArray(value) ? value : [];
    control = (
      <TupleInput
        envKey={envKey}
        itemSchemas={schema.items}
        value={tupleValue}
        onChange={(next) => onChange(next)}
      />
    );
  } else if (schema.type === "dict") {
    const dictValue =
      typeof value === "object" && value !== null && !Array.isArray(value)
        ? (value as Record<string, unknown>)
        : {};
    control = (
      <DictInput
        envKey={envKey}
        valueSchema={schema.value ?? { type: "str" }}
        value={dictValue}
        onChange={(next) => onChange(next)}
      />
    );
  } else if (schema.type === "union" && Array.isArray(schema.variants)) {
    control = (
      <UnionInput
        envKey={envKey}
        variants={schema.variants}
        value={value}
        onChange={(next) => onChange(next)}
      />
    );
  } else if (schema.type === "dataclass") {
    const objValue =
      typeof value === "object" && value !== null && !Array.isArray(value)
        ? (value as Record<string, unknown>)
        : {};
    control = (
      <DataclassInput
        envKey={envKey}
        schema={schema}
        value={objValue}
        onChange={(next) => onChange(next)}
      />
    );
  } else {
    control = (
      <input
        type="text"
        value={value === null || value === undefined ? "" : String(value)}
        onChange={(e) => onChange(e.target.value)}
        placeholder={schema.type === "path" ? "/path/to/..." : ""}
        className="w-full rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 font-mono text-xs outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
      />
    );
  }

  if (!schema.nullable) {
    return <>{control}</>;
  }

  return (
    <div className="flex items-start gap-2">
      <div className="min-w-0 flex-1">{control}</div>
      <button
        type="button"
        onClick={() => onChange(null)}
        className="shrink-0 rounded border border-zinc-300 px-2 py-1.5 text-xs text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
      >
        Set null
      </button>
    </div>
  );
}
