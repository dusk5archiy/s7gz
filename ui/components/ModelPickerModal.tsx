"use client";

import { useEffect, useMemo, useState } from "react";
import { XIcon } from "@/components/ActionIcons";
import type { FuelModelItem, FuelModelsListResponse } from "@/lib/types";

interface ModelPickerModalProps {
  open: boolean;
  currentRelativePath?: string;
  onSelect: (relativePath: string) => void;
  onClose: () => void;
}

function getModelFolderPrefix(item: FuelModelItem): string {
  const raw = item.display_path;
  const withoutVersion =
    item.version && raw.endsWith(`/${item.version}`)
      ? raw.slice(0, -(item.version.length + 1))
      : raw;
  const idx = withoutVersion.lastIndexOf("/");
  return idx < 0 ? "./" : `${withoutVersion.slice(0, idx)}/`;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function ModelPickerModal({
  open,
  currentRelativePath = "",
  onSelect,
  onClose,
}: ModelPickerModalProps) {
  const [data, setData] = useState<FuelModelsListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    fetch("/api/models")
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
        return (await res.json()) as FuelModelsListResponse;
      })
      .then((next) => {
        if (!cancelled) {
          setData(next);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  const loading = open && data === null && error === null;

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  const providers = useMemo(
    () => (data ? Object.values(data.providers) : []),
    [data],
  );

  const items = useMemo(() => {
    if (!data) {
      return [] as Array<{
        item: FuelModelItem;
        providerLabel: string;
        catalogRelPath: string;
      }>;
    }
    const q = search.trim().toLowerCase();
    const out: Array<{
      item: FuelModelItem;
      providerLabel: string;
      catalogRelPath: string;
    }> = [];

    for (const prov of providers) {
      if (activeTab !== "all" && prov.key !== activeTab) continue;
      for (const item of prov.source_models) {
        if (!item.has_sdf) continue;
        const catalogRelPath = `${item.relative_path}/model.sdf`;
        if (
          q &&
          !item.name.toLowerCase().includes(q) &&
          !item.display_path.toLowerCase().includes(q) &&
          !catalogRelPath.toLowerCase().includes(q) &&
          !prov.label.toLowerCase().includes(q)
        ) {
          continue;
        }
        out.push({ item, providerLabel: prov.label, catalogRelPath });
      }
    }
    return out;
  }, [data, providers, activeTab, search]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        className="flex max-h-[82vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-950"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <div>
            <h2 className="text-sm font-semibold">Model Catalog</h2>
            <p className="text-xs text-zinc-500">
              Select a model relative to source_models/ (patched variant is used automatically when available)
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-zinc-200 text-zinc-500 hover:bg-zinc-100 dark:border-zinc-800 dark:hover:bg-zinc-900"
          >
            <XIcon className="h-3.5 w-3.5" />
          </button>
        </header>

        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 px-4 py-2.5 dark:border-zinc-800">
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setActiveTab("all")}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                activeTab === "all"
                  ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
              }`}
            >
              All ({providers.reduce((s, p) => s + p.source_models.filter((m) => m.has_sdf).length, 0)})
            </button>
            {providers.map((prov) => (
              <button
                key={prov.key}
                type="button"
                onClick={() => setActiveTab(prov.key)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                  activeTab === prov.key
                    ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                    : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
                }`}
              >
                {prov.label} ({prov.source_models.filter((m) => m.has_sdf).length})
              </button>
            ))}
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter models..."
            className="w-52 rounded-md border border-zinc-300 bg-white px-2.5 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto divide-y divide-zinc-100 dark:divide-zinc-900">
          {loading ? (
            <div className="p-8 text-center text-xs text-zinc-500">Loading models...</div>
          ) : error ? (
            <div className="p-6 text-center font-mono text-xs text-rose-600 dark:text-rose-400">
              {error}
            </div>
          ) : items.length === 0 ? (
            <div className="p-8 text-center text-xs text-zinc-500">No models matched.</div>
          ) : (
            items.map(({ item, providerLabel, catalogRelPath }) => {
              const folderPrefix = getModelFolderPrefix(item);
              const isSelected = currentRelativePath === catalogRelPath;
              return (
                <button
                  key={catalogRelPath}
                  type="button"
                  onClick={() => {
                    onSelect(catalogRelPath);
                    onClose();
                  }}
                  className={`flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left transition ${
                    isSelected
                      ? "bg-emerald-50/70 dark:bg-emerald-950/30"
                      : "hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                        {providerLabel}
                      </span>
                      <span className="truncate font-mono text-[10px] text-zinc-500">
                        {folderPrefix}
                      </span>
                    </div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-2">
                      <span className="truncate font-mono text-xs font-semibold">
                        {item.name}
                      </span>
                      {item.version && (
                        <span className="font-mono text-[10px] text-zinc-500">
                          v{item.version}
                        </span>
                      )}
                      {item.is_patched && (
                        <span className="rounded bg-sky-500/15 px-1.5 py-0.5 font-mono text-[10px] text-sky-700 dark:text-sky-300">
                          Patched
                        </span>
                      )}
                      {isSelected && (
                        <span className="rounded bg-zinc-900 px-1.5 py-0.5 font-mono text-[10px] text-white dark:bg-zinc-100 dark:text-zinc-900">
                          Selected
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 truncate font-mono text-[10px] text-zinc-400">
                      {catalogRelPath}
                    </div>
                  </div>
                  <div className="shrink-0 text-right font-mono text-[11px] text-zinc-500">
                    {formatBytes(item.size_bytes)}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
