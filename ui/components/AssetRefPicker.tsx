"use client";

import { useState } from "react";
import { BookIcon, PlayIcon, ResetIcon, XIcon } from "@/components/ActionIcons";
import type { AssetRef } from "@/lib/types";

interface AssetRefPickerProps {
  value: AssetRef | null;
  canReset: boolean;
  disabled?: boolean;
  error?: string | null;
  catalogPlaceholder?: string;
  pathPlaceholder?: string;
  browseTitle?: string;
  resetTitle?: string;
  applyTitle?: string;
  cancelTitle?: string;
  onChange: (next: AssetRef | null) => void;
  onOpenCatalog: () => void;
  onReset: () => void;
}

export function AssetRefPicker({
  value,
  canReset,
  disabled = false,
  error,
  catalogPlaceholder = "px4/x500/model.sdf",
  pathPlaceholder = "runtime/... or /opt/ros/...",
  browseTitle = "Browse catalog",
  resetTitle = "Reset override",
  applyTitle = "Apply",
  cancelTitle = "Cancel edit",
  onChange,
  onOpenCatalog,
  onReset,
}: AssetRefPickerProps) {
  const [preferredMode, setPreferredMode] = useState<"catalog" | "path" | null>(null);
  const mode: "catalog" | "path" =
    preferredMode ?? (value?.kind === "path" ? "path" : "catalog");

  const committedText =
    mode === "catalog"
      ? value?.kind === "catalog"
        ? value.relative_path
        : ""
      : value?.kind === "path"
        ? value.path
        : "";

  const [draft, setDraft] = useState<{
    mode: "catalog" | "path";
    base: string;
    text: string;
  } | null>(null);

  const localText =
    draft && draft.mode === mode && draft.base === committedText
      ? draft.text
      : committedText;
  const isEditing = localText !== committedText;

  const handleModeSwitch = (nextMode: "catalog" | "path") => {
    if (disabled || nextMode === mode) return;
    setDraft(null);
    setPreferredMode(nextMode);
  };

  const handleApply = () => {
    if (disabled) return;
    const trimmed = localText.trim();
    setDraft(null);
    setPreferredMode(null);
    if (!trimmed) {
      onChange(null);
    } else if (mode === "catalog") {
      onChange({ kind: "catalog", relative_path: trimmed.replace(/^\/+/, "") });
    } else {
      onChange({ kind: "path", path: trimmed });
    }
  };

  const handleCancel = () => {
    setDraft(null);
  };

  return (
    <div className="w-full space-y-1.5">
      <div className="flex items-center gap-1.5">
        <div
          className="inline-flex h-8 shrink-0 items-center rounded-md border border-zinc-200 bg-zinc-50 p-0.5 text-[11px] dark:border-zinc-800 dark:bg-zinc-900"
          role="group"
          aria-label="Reference mode"
        >
          <button
            type="button"
            disabled={disabled}
            onClick={() => handleModeSwitch("catalog")}
            className={`rounded px-2 py-0.5 font-medium transition ${
              mode === "catalog"
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
            }`}
          >
            Catalog
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={() => handleModeSwitch("path")}
            className={`rounded px-2 py-0.5 font-medium transition ${
              mode === "path"
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
            }`}
          >
            Path
          </button>
        </div>

        <input
          type="text"
          value={localText}
          disabled={disabled}
          placeholder={mode === "catalog" ? catalogPlaceholder : pathPlaceholder}
          onChange={(e) => {
            const nextText = e.target.value;
            setDraft(
              nextText === committedText
                ? null
                : { mode, base: committedText, text: nextText },
            );
          }}
          onKeyDown={(e) => {
            if (isEditing && e.key === "Enter") {
              e.preventDefault();
              handleApply();
            } else if (isEditing && e.key === "Escape") {
              e.preventDefault();
              handleCancel();
            }
          }}
          className={`min-w-0 flex-1 rounded-md border px-2.5 py-1.5 font-mono text-xs transition outline-none disabled:opacity-50 ${
            isEditing
              ? "border-amber-400 bg-amber-50/40 ring-1 ring-amber-400/70 focus:border-amber-500 dark:border-amber-400 dark:bg-amber-950/20"
              : error
                ? "border-rose-500 bg-white focus:border-rose-500 dark:bg-zinc-900"
                : "border-zinc-300 bg-white focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:focus:border-zinc-500"
          }`}
        />

        {isEditing ? (
          <>
            <button
              type="button"
              disabled={disabled}
              onClick={handleApply}
              aria-label={applyTitle}
              title={applyTitle}
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-amber-500 bg-amber-400 text-zinc-950 transition hover:bg-amber-300 disabled:opacity-50"
            >
              <PlayIcon className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={handleCancel}
              aria-label={cancelTitle}
              title={cancelTitle}
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-zinc-300 bg-white text-rose-600 transition hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-rose-400 dark:hover:bg-zinc-800"
            >
              <XIcon className="h-3.5 w-3.5" />
            </button>
          </>
        ) : (
          <>
            {mode === "catalog" && (
              <button
                type="button"
                disabled={disabled}
                onClick={() => {
                  setPreferredMode(null);
                  setDraft(null);
                  onOpenCatalog();
                }}
                aria-label={browseTitle}
                title={browseTitle}
                className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-emerald-600 bg-emerald-600 text-white transition hover:bg-emerald-500 disabled:opacity-50"
              >
                <BookIcon className="h-3.5 w-3.5" />
              </button>
            )}
            <button
              type="button"
              disabled={disabled || !canReset}
              onClick={() => {
                setPreferredMode(null);
                setDraft(null);
                onReset();
              }}
              aria-label={resetTitle}
              title={canReset ? resetTitle : "Nothing to reset"}
              className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border transition ${
                disabled || !canReset
                  ? "cursor-not-allowed border-zinc-400 bg-zinc-400 text-white dark:border-zinc-600 dark:bg-zinc-600 dark:text-white"
                  : "border-blue-600 bg-blue-600 text-white hover:bg-blue-500"
              }`}
            >
              <ResetIcon className="h-3.5 w-3.5" />
            </button>
          </>
        )}
      </div>
      {error && (
        <span className="block text-[11px] text-rose-600 dark:text-rose-400">
          {error}
        </span>
      )}
    </div>
  );
}
