"use client";

import { useState } from "react";
import { FolderIcon } from "@/components/ActionIcons";
import {
  CompositeExplorerModal,
  summarizeCompositeValue,
} from "@/components/CompositeExplorerModal";
import { FieldInput, getCompositeDepth } from "@/components/FieldInput";
import {
  deepEqual,
  formatSchemaSummary,
  isFieldOverridden,
} from "@/lib/settings-utils";
import type { SettingsField, SettingsGroup } from "@/lib/types";

interface SettingsGroupPanelProps {
  group: SettingsGroup;
  drafts: Record<string, unknown>;
  onFieldChange: (envKey: string, nextValue: unknown) => void;
  onUndoField: (envKey: string) => void;
  onClearOverride: (envKey: string) => void;
}

export function SettingsGroupPanel({
  group,
  drafts,
  onFieldChange,
  onUndoField,
  onClearOverride,
}: SettingsGroupPanelProps) {
  const [explorerField, setExplorerField] = useState<SettingsField | null>(null);
  const overriddenCount = group.fields.filter(isFieldOverridden).length;
  const dirtyCount = group.fields.filter(
    (f) => f.env_key in drafts && !deepEqual(drafts[f.env_key], f.value),
  ).length;

  const explorerCurrentValue = explorerField
    ? explorerField.env_key in drafts
      ? drafts[explorerField.env_key]
      : explorerField.value
    : undefined;

  return (
    <section className="rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <div>
          <h2 className="text-base font-semibold">{group.group}</h2>
          <code className="text-xs text-zinc-500">{group.prefix}*</code>
          {group.description && (
            <p className="mt-1 whitespace-pre-line text-xs text-zinc-600 dark:text-zinc-400">
              {group.description}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs">
          {dirtyCount > 0 && (
            <span className="rounded-full bg-blue-100 px-2 py-0.5 font-medium text-blue-800 dark:bg-blue-950 dark:text-blue-300">
              {dirtyCount} unsaved
            </span>
          )}
          {overriddenCount > 0 && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-300">
              {overriddenCount} overridden
            </span>
          )}
          <span className="text-zinc-500">{group.fields.length} fields</span>
        </div>
      </header>

      <div className="divide-y divide-zinc-100 dark:divide-zinc-900">
        {group.fields.map((field) => {
          const hasDefault = field.has_default !== false;
          const hasDraft = field.env_key in drafts;
          const currentValue = hasDraft ? drafts[field.env_key] : field.value;
          const isDirty = hasDraft && !deepEqual(currentValue, field.value);
          const uiOverridden = field.is_ui_overridden === true;
          const envCustomized =
            hasDefault &&
            field.base_value !== undefined &&
            !deepEqual(field.base_value, field.default);
          const differsFromDefault =
            hasDefault && !deepEqual(currentValue, field.default);
          const useExplorerModal = getCompositeDepth(field.schema) >= 2;

          return (
            <div
              key={field.env_key}
              className={`grid gap-3 px-4 py-3 sm:grid-cols-12 sm:items-start ${
                isDirty
                  ? "bg-blue-50/40 dark:bg-blue-950/15"
                  : uiOverridden
                    ? "bg-amber-50/40 dark:bg-amber-950/15"
                    : ""
              }`}
            >
              <div className="min-w-0 space-y-1 sm:col-span-5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{field.name}</span>
                  {isDirty && (
                    <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[11px] font-medium text-blue-800 dark:bg-blue-950 dark:text-blue-300">
                      unsaved
                    </span>
                  )}
                  {uiOverridden ? (
                    <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                      ui override
                    </span>
                  ) : envCustomized ? (
                    <span className="rounded bg-sky-100 px-1.5 py-0.5 text-[11px] font-medium text-sky-800 dark:bg-sky-950 dark:text-sky-300">
                      env
                    </span>
                  ) : !hasDefault ? (
                    <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[11px] text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
                      required
                    </span>
                  ) : (
                    <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[11px] text-zinc-500 dark:bg-zinc-900">
                      default
                    </span>
                  )}
                </div>
                <div className="break-all font-mono text-xs text-zinc-500">
                  {field.env_key}
                </div>
                {field.description && (
                  <p className="whitespace-pre-line text-xs text-zinc-600 dark:text-zinc-400">
                    {field.description}
                  </p>
                )}
                <div className="text-xs text-zinc-500">
                  {formatSchemaSummary(field.schema)}
                </div>
              </div>

              <div className="min-w-0 space-y-1.5 sm:col-span-7">
                {useExplorerModal ? (
                  <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-zinc-200 bg-zinc-50/70 px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900/50">
                    <div className="flex min-w-0 items-center gap-2">
                      <FolderIcon className="h-4 w-4 shrink-0 text-amber-500 dark:text-amber-400" />
                      <span className="truncate font-mono text-xs text-zinc-700 dark:text-zinc-300">
                        {summarizeCompositeValue(field.schema, currentValue)}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setExplorerField(field)}
                      className="shrink-0 rounded-md bg-zinc-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
                    >
                      Open Explorer
                    </button>
                  </div>
                ) : (
                  <FieldInput
                    envKey={field.env_key}
                    schema={field.schema}
                    value={currentValue}
                    onChange={(next) => onFieldChange(field.env_key, next)}
                  />
                )}
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-500">
                  <div className="min-w-0 space-y-0.5 font-mono">
                    <div className="break-all">
                      {hasDefault
                        ? `default: ${JSON.stringify(field.default)}`
                        : "no default (required)"}
                    </div>
                    {field.base_value !== undefined &&
                      (!hasDefault || envCustomized) && (
                        <div className="break-all text-sky-700 dark:text-sky-400">
                          base env: {JSON.stringify(field.base_value)}
                        </div>
                      )}
                  </div>
                  <div className="flex items-center gap-2">
                    {isDirty && (
                      <button
                        type="button"
                        onClick={() => onUndoField(field.env_key)}
                        className="text-blue-600 hover:underline dark:text-blue-400"
                      >
                        Undo edit
                      </button>
                    )}
                    {uiOverridden && (
                      <button
                        type="button"
                        onClick={() => onClearOverride(field.env_key)}
                        className="text-amber-700 hover:underline dark:text-amber-400"
                      >
                        Clear override
                      </button>
                    )}
                    {differsFromDefault && (
                      <button
                        type="button"
                        onClick={() => onFieldChange(field.env_key, field.default)}
                        className="text-zinc-600 hover:underline dark:text-zinc-400"
                      >
                        Reset default
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {explorerField && (
        <CompositeExplorerModal
          key={explorerField.env_key}
          open={true}
          title={explorerField.env_key}
          subtitle={explorerField.description}
          schema={explorerField.schema}
          value={explorerCurrentValue}
          onApply={(nextVal) => onFieldChange(explorerField.env_key, nextVal)}
          onClose={() => setExplorerField(null)}
        />
      )}
    </section>
  );
}
