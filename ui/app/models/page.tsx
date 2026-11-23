"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CubeIcon,
  DownloadIcon,
  FileIcon,
  InfoIcon,
  ToolsIcon,
  TrashIcon,
} from "@/components/ActionIcons";
import { FuelModelPreviewModal } from "@/components/FuelModelPreviewModal";
import { FuelModelThumbnail } from "@/components/FuelModelThumbnail";
import { DISABLED_BUSY_BTN_CLASS, useFuelTerminal } from "@/components/FuelProgressPanel";
import { ItemInfoModal, type ItemInfoRow } from "@/components/ItemInfoModal";
import { SdfViewerModal } from "@/components/SdfViewerModal";
import type {
  FuelModelItem,
  FuelModelReadResponse,
  FuelModelScope,
  FuelModelsListResponse,
  ModelProviderGroup,
} from "@/lib/types";

function encodeRelPath(relPath: string): string {
  return relPath.split("/").map(encodeURIComponent).join("/");
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

export default function ModelsPage() {
  const [activeTab, setActiveTab] = useState<string>("fuel");
  const [data, setData] = useState<FuelModelsListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [modelNameInput, setModelNameInput] = useState("");
  const [modelUrlInput, setModelUrlInput] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [syncingProvider, setSyncingProvider] = useState<string | null>(null);
  const [patchingPath, setPatchingPath] = useState<string | null>(null);
  const [redownloadingKey, setRedownloadingKey] = useState<string | null>(null);

  const [inspected, setInspected] = useState<FuelModelReadResponse | null>(null);
  const [inspectLoading, setInspectLoading] = useState(false);
  const [previewTarget, setPreviewTarget] = useState<{
    relativePath: string;
    scope: FuelModelScope;
  } | null>(null);
  const [infoModal, setInfoModal] = useState<{
    title: string;
    subtitle?: string;
    rows: ItemInfoRow[];
  } | null>(null);
  const { busy, runTask } = useFuelTerminal();

  const refreshModels = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/models");
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      setData((await res.json()) as FuelModelsListResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
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
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleDownload = async (e: React.FormEvent) => {
    e.preventDefault();
    setDownloading(true);
    try {
      const next = await runTask<FuelModelsListResponse & { downloaded?: string }>({
        action: "model_download",
        model_name: modelNameInput.trim() || null,
        model_url: modelUrlInput.trim() || null,
      });
      setData(next);
      setModelNameInput("");
      setModelUrlInput("");
    } catch {
      // Displayed in terminal modal.
    } finally {
      setDownloading(false);
    }
  };

  const handleSyncProvider = async (providerKey: string) => {
    setSyncingProvider(providerKey);
    try {
      const next = await runTask<FuelModelsListResponse>({
        action: "model_provider_sync",
        provider: providerKey,
      });
      setData(next);
    } catch {
      // Displayed in terminal modal.
    } finally {
      setSyncingProvider(null);
    }
  };

  const handlePatch = async (relativePath: string) => {
    setPatchingPath(relativePath);
    try {
      const next = await runTask<FuelModelsListResponse & { repaired?: boolean }>({
        action: "model_patch",
        relative_path: relativePath,
      });
      setData(next);
    } catch {
      // Displayed in terminal modal.
    } finally {
      setPatchingPath(null);
    }
  };

  const handleRedownload = async (relativePath: string, scope: FuelModelScope) => {
    const key = `${scope}:${relativePath}`;
    setRedownloadingKey(key);
    try {
      const next = await runTask<FuelModelsListResponse & { redownloaded?: string }>({
        action: "model_redownload",
        relative_path: relativePath,
        scope,
      });
      setData(next);
    } catch {
      // Displayed in terminal modal.
    } finally {
      setRedownloadingKey(null);
    }
  };

  const handleInspect = async (relativePath: string, scope: FuelModelScope) => {
    setInspectLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/models/sdf/${encodeRelPath(relativePath)}?scope=${scope}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      setInspected((await res.json()) as FuelModelReadResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setInspectLoading(false);
    }
  };

  const handleDelete = async (relativePath: string, scope: FuelModelScope) => {
    if (busy || !window.confirm(`Delete ${scope} model "${relativePath}"?`)) return;
    try {
      const next = await runTask<FuelModelsListResponse>(
        {
          action: "model_delete",
          relative_path: relativePath,
          scope,
        },
        { openTerminal: false },
      );
      setData(next);
      if (inspected?.relative_path === relativePath && inspected?.scope === scope) {
        setInspected(null);
      }
    } catch {
      // Displayed in terminal modal.
    }
  };

  const openModelInfo = (
    item: FuelModelItem,
    provider: ModelProviderGroup,
    scope: FuelModelScope,
  ) => {
    const stage = scope === "patched" ? "Patched" : "Source";
    const rootDir = scope === "patched" ? data?.patched_dir ?? "" : data?.source_dir ?? "";
    const fullPath = `${rootDir.replace(/\/+$/, "")}/${item.relative_path}`;
    const files: string[] = [];
    if (item.has_sdf) files.push("model.sdf");
    if (item.has_config) files.push("model.config");
    const rows: ItemInfoRow[] = [
      { label: "Name", value: item.name, mono: true },
      { label: "Origin", value: provider.label },
      { label: "Stage", value: stage },
    ];
    if (item.owner && item.server) {
      rows.push({
        label: "Owner / Server",
        value: `${item.owner} (${item.server})`,
        mono: true,
      });
    }
    if (item.version) {
      rows.push({ label: "Version", value: `v${item.version}`, mono: true });
    }
    rows.push(
      { label: "Relative Path", value: item.relative_path, mono: true, copyable: true },
      { label: "Full Path", value: fullPath, mono: true, copyable: true },
    );
    if (item.sdf_rel_path) {
      rows.push({
        label: "Model SDF Path",
        value: item.sdf_rel_path,
        mono: true,
        copyable: true,
      });
    }
    rows.push(
      {
        label: "Size",
        value: `${formatBytes(item.size_bytes)} (${item.size_bytes.toLocaleString()} bytes)`,
        mono: true,
      },
      { label: "Files", value: files.length ? files.join(", ") : "—", mono: true },
      { label: "Modified", value: new Date(item.modified_at).toLocaleString() },
      { label: "Patched", value: scope === "patched" || item.is_patched ? "Yes" : "No" },
      { label: "3D Mesh", value: item.has_3d === false ? "No" : "Yes" },
    );
    if (item.missing_files && item.missing_files.length > 0) {
      rows.push({
        label: "Missing Files",
        value: item.missing_files.join(", "),
        mono: true,
      });
    }
    setInfoModal({
      title: item.name,
      subtitle: `${provider.label} · ${stage}`,
      rows,
    });
  };

  const providerList = data ? Object.values(data.providers) : [];
  const activeProvider =
    data?.providers[activeTab] ?? providerList[0] ?? null;

  const renderModelSection = (
    provider: ModelProviderGroup,
    scope: FuelModelScope,
    items: FuelModelItem[],
  ) => {
    const isPatched = scope === "patched";
    const relDir = isPatched ? provider.patched_rel_dir : provider.source_rel_dir;
    const canDelete = isPatched || provider.can_delete_source;
    const title = isPatched
      ? `Patched ${provider.label} Models`
      : `Source ${provider.label} Models`;

    return (
      <section className="rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <div className="min-w-0">
            <h2 className="text-base font-semibold">
              {title} ({items.length})
            </h2>
            <code className="break-all text-xs text-zinc-500">{relDir}</code>
          </div>
          <span className="text-xs text-zinc-500">{items.length} model(s)</span>
        </header>
        <div className="p-4">
          {items.length > 0 ? (
            <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
              {items.map((item) => {
                const folderPrefix = getModelFolderPrefix(item);
                return (
                  <div
                    key={`${scope}:${item.relative_path}`}
                    className={`flex flex-col overflow-hidden rounded-lg border ${
                      isPatched
                        ? "border-emerald-300/70 bg-emerald-50/20 dark:border-emerald-900/60 dark:bg-emerald-950/10"
                        : "border-zinc-200 bg-zinc-50/50 dark:border-zinc-800 dark:bg-zinc-900/40"
                    }`}
                  >
                    <button
                      type="button"
                      disabled={!item.has_sdf || item.has_3d === false}
                      onClick={() =>
                        setPreviewTarget({ relativePath: item.relative_path, scope })
                      }
                      title={
                        !item.has_sdf || item.has_3d === false
                          ? "No 3D mesh"
                          : "Open 3D Model Viewer"
                      }
                      className="block w-full cursor-pointer text-left transition hover:opacity-90 disabled:cursor-default disabled:hover:opacity-100"
                    >
                      {item.has_sdf ? (
                        <FuelModelThumbnail
                          relativePath={item.relative_path}
                          scope={scope}
                          thumbnailUrl={item.thumbnail_url}
                        />
                      ) : (
                        <div className="flex aspect-[16/10] w-full items-center justify-center rounded-t-lg bg-[#0b1017] font-mono text-[11px] text-zinc-500">
                          No 3D mesh
                        </div>
                      )}
                    </button>
                    <div className="flex flex-1 flex-col justify-between gap-2 p-3">
                      <div>
                        <div
                          className="truncate font-mono text-[10px] text-zinc-500"
                          title={item.relative_path}
                        >
                          {folderPrefix}
                        </div>
                        <div
                          className="truncate font-mono text-xs font-semibold"
                          title={item.name}
                        >
                          {item.name}
                        </div>
                        <div className="mt-0.5 truncate font-mono text-[11px] text-zinc-500">
                          {item.version ? `v${item.version} · ` : ""}
                          {formatBytes(item.size_bytes)}
                          {!item.version && item.has_sdf ? " · model.sdf" : ""}
                        </div>
                        {item.missing_files && item.missing_files.length > 0 && (
                          <div
                            className="mt-1 inline-block rounded bg-amber-500/15 px-1.5 py-0.5 font-mono text-[10px] text-amber-700 dark:text-amber-300"
                            title={`Missing files:\n${item.missing_files.join("\n")}`}
                          >
                            Incomplete ({item.missing_files.length} missing)
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5">
                        {item.has_sdf && (
                          <>
                            <button
                              type="button"
                              disabled={item.has_3d === false}
                              onClick={() =>
                                setPreviewTarget({ relativePath: item.relative_path, scope })
                              }
                              aria-label={item.has_3d === false ? "No 3D mesh" : "3D Preview"}
                              title={item.has_3d === false ? "No 3D mesh" : "3D Preview"}
                              className={`inline-flex items-center justify-center rounded border px-2 py-1 text-xs font-medium ${
                                item.has_3d === false
                                  ? DISABLED_BUSY_BTN_CLASS
                                  : "border-transparent bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
                              }`}
                            >
                              <CubeIcon />
                            </button>
                            <button
                              type="button"
                              disabled={busy || patchingPath === item.relative_path}
                              onClick={() => void handlePatch(item.relative_path)}
                              aria-label={isPatched || item.is_patched ? "Re-patch" : "Patch"}
                              title={
                                isPatched
                                  ? "Re-patch"
                                  : item.is_patched
                                    ? "Re-patch (Patched)"
                                    : "Patch (Not patched)"
                              }
                              className={`inline-flex items-center justify-center rounded border px-2 py-1 text-xs ${
                                busy
                                  ? DISABLED_BUSY_BTN_CLASS
                                  : !isPatched && !item.is_patched
                                    ? "border-amber-400 bg-amber-400 text-zinc-950 hover:bg-amber-300 disabled:opacity-50"
                                    : "border-zinc-300 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
                              }`}
                            >
                              <ToolsIcon />
                            </button>
                            <button
                              type="button"
                              disabled={
                                busy || redownloadingKey === `${scope}:${item.relative_path}`
                              }
                              onClick={() => void handleRedownload(item.relative_path, scope)}
                              aria-label="Re-download"
                              title="Re-download"
                              className={`inline-flex items-center justify-center rounded border px-2 py-1 text-xs ${
                                busy
                                  ? DISABLED_BUSY_BTN_CLASS
                                  : "border-zinc-300 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
                              }`}
                            >
                              <DownloadIcon />
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleInspect(item.relative_path, scope)}
                              aria-label="Inspect SDF"
                              title="Inspect SDF"
                              className="inline-flex flex-1 items-center justify-center rounded border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
                            >
                              <FileIcon />
                            </button>
                          </>
                        )}
                        <button
                          type="button"
                          onClick={() => openModelInfo(item, provider, scope)}
                          aria-label="Info"
                          title="Info"
                          className={`inline-flex items-center justify-center rounded border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800 ${
                            !item.has_sdf ? "ml-auto" : ""
                          }`}
                        >
                          <InfoIcon />
                        </button>
                        {canDelete && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => void handleDelete(item.relative_path, scope)}
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
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="py-6 text-center text-xs text-zinc-500">
              {loading
                ? "Loading..."
                : isPatched
                  ? `No patched ${provider.label} models yet. Click Patch on a source model below.`
                  : `No source ${provider.label} models found.`}
            </div>
          )}
        </div>
      </section>
    );
  };

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-6">
      <header className="space-y-3 border-b border-zinc-200 pb-4 dark:border-zinc-800">
        <div>
          <h1 className="text-2xl font-semibold">Models</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Manage source &amp; patched models across providers, inspect SDF files, and preview 3D meshes
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {activeProvider?.supports_sync && (
            <button
              type="button"
              onClick={() => void handleSyncProvider(activeProvider.key)}
              disabled={busy || syncingProvider === activeProvider.key}
              className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
                busy
                  ? DISABLED_BUSY_BTN_CLASS
                  : "border-zinc-300 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
              }`}
            >
              {syncingProvider === activeProvider.key
                ? `Syncing ${activeProvider.label}...`
                : `Sync All ${activeProvider.label} Models`}
            </button>
          )}
          <button
            type="button"
            onClick={() => void refreshModels()}
            disabled={loading}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </header>

      {data && activeProvider && (
        <div className="flex items-center gap-1 border-b border-zinc-200 dark:border-zinc-800">
          {providerList.map((prov) => (
            <button
              key={prov.key}
              type="button"
              onClick={() => setActiveTab(prov.key)}
              className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
                activeProvider.key === prov.key
                  ? "border-zinc-900 text-zinc-900 dark:border-zinc-100 dark:text-zinc-100"
                  : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
              }`}
            >
              {prov.label} Models ({prov.source_models.length})
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          {error}
        </div>
      )}

      {data && activeProvider && (
        <>
          {activeProvider.supports_download && (
            <form
              onSubmit={(e) => void handleDownload(e)}
              className="space-y-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
            >
              <h2 className="text-sm font-semibold">Download from {activeProvider.label}</h2>
              <div className="grid gap-2 sm:grid-cols-2">
                <input
                  type="text"
                  value={modelNameInput}
                  onChange={(e) => setModelNameInput(e.target.value)}
                  placeholder="owner/model_name (e.g. OpenRobotics/Base Station)"
                  className="rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-900"
                />
                <input
                  type="text"
                  value={modelUrlInput}
                  onChange={(e) => setModelUrlInput(e.target.value)}
                  placeholder="or full Fuel URL (https://fuel.gazebosim.org/...)"
                  className="rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-900"
                />
              </div>
              <button
                type="submit"
                disabled={busy || downloading || (!modelNameInput.trim() && !modelUrlInput.trim())}
                className={`rounded-md border px-3 py-1.5 text-xs font-medium ${
                  busy
                    ? DISABLED_BUSY_BTN_CLASS
                    : "border-transparent bg-zinc-900 text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
                }`}
              >
                {downloading ? "Downloading..." : "Download"}
              </button>
            </form>
          )}

          {renderModelSection(activeProvider, "patched", activeProvider.patched_models)}
          {renderModelSection(activeProvider, "source", activeProvider.source_models)}
        </>
      )}

      <SdfViewerModal
        open={inspectLoading || Boolean(inspected)}
        title={
          inspectLoading
            ? "Loading model.sdf..."
            : `[${inspected?.scope ?? "source"}] ${inspected?.relative_path}/model.sdf (${formatBytes(inspected?.size_bytes ?? 0)})`
        }
        content={inspected?.content ?? null}
        loading={inspectLoading}
        onClose={() => setInspected(null)}
      />
      <FuelModelPreviewModal
        relativePath={previewTarget?.relativePath ?? null}
        scope={previewTarget?.scope ?? "source"}
        onClose={() => setPreviewTarget(null)}
      />
      <ItemInfoModal
        open={Boolean(infoModal)}
        title={infoModal?.title ?? ""}
        subtitle={infoModal?.subtitle}
        rows={infoModal?.rows ?? []}
        onClose={() => setInfoModal(null)}
      />
    </main>
  );
}
