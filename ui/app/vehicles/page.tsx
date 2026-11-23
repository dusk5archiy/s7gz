"use client";

import { useCallback, useEffect, useState } from "react";
import { FileIcon, TrashIcon } from "@/components/ActionIcons";
import { DISABLED_BUSY_BTN_CLASS, useFuelTerminal } from "@/components/FuelProgressPanel";
import { SdfViewerModal } from "@/components/SdfViewerModal";
import type {
  VehicleModelItem,
  VehicleModelReadResponse,
  VehicleModelsListResponse,
} from "@/lib/types";

function encodeRelPath(relPath: string): string {
  return relPath.split("/").map(encodeURIComponent).join("/");
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function VehiclesPage() {
  const [data, setData] = useState<VehicleModelsListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inspected, setInspected] = useState<VehicleModelReadResponse | null>(null);
  const [inspectLoading, setInspectLoading] = useState(false);
  const { busy, runTask } = useFuelTerminal();

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const modelsRes = await fetch("/api/vehicles/models");
      if (!modelsRes.ok) throw new Error(`HTTP ${modelsRes.status}: ${await modelsRes.text()}`);
      const modelsJson = (await modelsRes.json()) as VehicleModelsListResponse;
      setData(modelsJson);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/vehicles/models")
      .then(async (modelsRes) => {
        if (!modelsRes.ok) throw new Error(`HTTP ${modelsRes.status}: ${await modelsRes.text()}`);
        return (await modelsRes.json()) as VehicleModelsListResponse;
      })
      .then((modelsJson) => {
        if (!cancelled) {
          setData(modelsJson);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const next = await runTask<VehicleModelsListResponse & { generated?: string[] }>({
        action: "vehicle_generate",
      });
      setData(next);
    } catch {
      // Result and error are displayed in the Fuel terminal modal.
    } finally {
      setGenerating(false);
    }
  };

  const handleInspect = async (relPath: string) => {
    setInspectLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/vehicles/models/generated/${encodeRelPath(relPath)}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      const next = (await res.json()) as VehicleModelReadResponse;
      setInspected(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setInspectLoading(false);
    }
  };

  const handleDelete = async (relPath: string) => {
    if (busy || !window.confirm(`Delete generated model "${relPath}"?`)) {
      return;
    }
    try {
      const next = await runTask<VehicleModelsListResponse>(
        {
          action: "vehicle_delete",
          scope: "generated",
          model_name: relPath,
        },
        { openTerminal: false },
      );
      setData(next);
      if (inspected?.relative_path === relPath) {
        setInspected(null);
      }
    } catch {
      // Result and error are displayed in the Fuel terminal modal.
    }
  };

  const renderModelRow = (item: VehicleModelItem) => (
    <tr
      key={`generated:${item.relative_path}`}
      className="border-t border-zinc-200 dark:border-zinc-800"
    >
      <td className="px-3 py-2 font-mono text-xs font-medium">{item.name}</td>
      <td className="px-3 py-2 text-xs text-zinc-500">
        {item.has_sdf ? "model.sdf" : "—"}
        {item.has_config ? " · model.config" : ""}
      </td>
      <td className="px-3 py-2 font-mono text-xs text-zinc-500">
        {formatBytes(item.size_bytes)}
      </td>
      <td className="px-3 py-2 text-xs text-zinc-500">
        {new Date(item.modified_at).toLocaleString()}
      </td>
      <td className="px-3 py-2 text-right">
        <div className="inline-flex items-center gap-2">
          {item.has_sdf && (
            <button
              type="button"
              onClick={() => void handleInspect(item.relative_path)}
              aria-label="Inspect SDF"
              title="Inspect SDF"
              className="inline-flex items-center justify-center rounded border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
            >
              <FileIcon />
            </button>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={() => void handleDelete(item.relative_path)}
            aria-label="Delete"
            title="Delete"
            className={`inline-flex items-center justify-center rounded border px-2 py-1 text-xs ${
              busy
                ? DISABLED_BUSY_BTN_CLASS
                : "border-rose-300 text-rose-600 hover:bg-rose-50 dark:border-rose-900/60 dark:text-rose-400 dark:hover:bg-rose-950/40"
            }`}
          >
            <TrashIcon />
          </button>
        </div>
      </td>
    </tr>
  );

  const worldGroups = data?.worlds ?? [];

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-6">
      <header className="space-y-3 border-b border-zinc-200 pb-4 dark:border-zinc-800">
        <div>
          <h1 className="text-2xl font-semibold">Vehicle Models</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Per-world generated SDF vehicle packages isolated under{" "}
            <code className="font-mono text-xs">
              {data?.generated_models_dir ?? "runtime/generated_models"}
            </code>
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {data?.active_world_key && (
            <span className="mr-auto rounded bg-emerald-500/15 px-2.5 py-1 font-mono text-xs text-emerald-700 dark:text-emerald-300">
              Active World: {data.active_world_key}
            </span>
          )}
          <button
            type="button"
            onClick={() => void loadAll()}
            disabled={loading}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            Refresh
          </button>
          <button
            type="button"
            onClick={() => void handleGenerate()}
            disabled={busy || generating}
            className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
              busy
                ? DISABLED_BUSY_BTN_CLASS
                : "border-transparent bg-zinc-900 text-white hover:bg-zinc-800 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
            }`}
          >
            {generating ? "Generating..." : "Generate Active World Models"}
          </button>
        </div>
      </header>

      {error && (
        <div className="rounded-md border border-rose-300 bg-rose-50 px-4 py-2.5 text-sm text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300">
          {error}
        </div>
      )}

      {worldGroups.length > 0 ? (
        <div className="space-y-4">
          {worldGroups.map((group) => {
            const isActive =
              Boolean(data?.active_world_key) &&
              group.world_key === data?.active_world_key;
            return (
              <section
                key={group.world_scope}
                className="rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="font-mono text-sm font-semibold">
                        {group.world_key}
                      </h2>
                      {isActive && (
                        <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 font-mono text-[10px] text-emerald-700 dark:text-emerald-300">
                          Active World
                        </span>
                      )}
                      <span className="text-xs text-zinc-500">
                        ({group.models.length} model{group.models.length === 1 ? "" : "s"})
                      </span>
                    </div>
                    <p className="mt-0.5 font-mono text-[11px] text-zinc-500">
                      {group.dir_rel}
                    </p>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead className="bg-zinc-50 text-[11px] uppercase text-zinc-500 dark:bg-zinc-900/50">
                      <tr>
                        <th className="px-3 py-2">Model</th>
                        <th className="px-3 py-2">Package</th>
                        <th className="px-3 py-2">Size</th>
                        <th className="px-3 py-2">Modified</th>
                        <th className="px-3 py-2 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.models.map((item) => renderModelRow(item))}
                    </tbody>
                  </table>
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <section className="rounded-lg border border-dashed border-zinc-300 bg-white p-8 text-center text-xs text-zinc-500 dark:border-zinc-700 dark:bg-zinc-950">
          {loading
            ? "Loading..."
            : "No generated vehicle models found. Click Generate Active World Models or patch a world with a fleet."}
        </section>
      )}

      <SdfViewerModal
        open={inspectLoading || Boolean(inspected)}
        title={
          inspectLoading
            ? "Loading model.sdf..."
            : `${inspected?.relative_path ?? inspected?.name}/model.sdf (${formatBytes(inspected?.size_bytes ?? 0)})`
        }
        content={inspected?.content ?? null}
        loading={inspectLoading}
        onClose={() => setInspected(null)}
      />
    </main>
  );
}
