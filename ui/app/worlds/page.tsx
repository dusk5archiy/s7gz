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
import { ItemInfoModal, type ItemInfoRow } from "@/components/ItemInfoModal";
import { SdfViewerModal } from "@/components/SdfViewerModal";
import { UiJsonModal } from "@/components/UiJsonModal";
import { DISABLED_BUSY_BTN_CLASS, useFuelTerminal } from "@/components/FuelProgressPanel";
import { WorldPreviewModal } from "@/components/WorldPreviewModal";
import { WorldThumbnail } from "@/components/WorldThumbnail";
import type {
  WorldFileItem,
  WorldProviderGroup,
  WorldReadResponse,
  WorldScope,
  WorldsListResponse,
} from "@/lib/types";

function encodeRelPath(relPath: string): string {
  return relPath.split("/").map(encodeURIComponent).join("/");
}

function splitRelPath(relPath: string): { dir: string; file: string } {
  const idx = relPath.lastIndexOf("/");
  if (idx < 0) return { dir: "", file: relPath };
  return { dir: relPath.slice(0, idx), file: relPath.slice(idx + 1) };
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

export default function WorldsPage() {
  const [data, setData] = useState<WorldsListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<string>("fuel");
  const [worldNameInput, setWorldNameInput] = useState("");
  const [worldUrlInput, setWorldUrlInput] = useState("");
  const [selectOnDownload, setSelectOnDownload] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [syncingProvider, setSyncingProvider] = useState<string | null>(null);
  const [patchingPath, setPatchingPath] = useState<string | null>(null);
  const [redownloadingPath, setRedownloadingPath] = useState<string | null>(null);
  const { busy, runTask } = useFuelTerminal();

  const [inspected, setInspected] = useState<WorldReadResponse | null>(null);
  const [inspectLoading, setInspectLoading] = useState(false);
  const [showJsonModal, setShowJsonModal] = useState(false);
  const [infoModal, setInfoModal] = useState<{
    title: string;
    subtitle?: string;
    rows: ItemInfoRow[];
  } | null>(null);
  const [previewTarget, setPreviewTarget] = useState<{
    relativePath: string;
    scope: WorldScope;
  } | null>(null);

  const refreshWorlds = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/worlds");
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      setData((await res.json()) as WorldsListResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/worlds")
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
        return (await res.json()) as WorldsListResponse;
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
      await runTask<{ relative_path: string }>({
        action: "world_download",
        world_name: worldNameInput.trim() || null,
        world_url: worldUrlInput.trim() || null,
        select: selectOnDownload,
      });
      setWorldNameInput("");
      setWorldUrlInput("");
      await refreshWorlds();
    } catch {
      // Displayed in terminal modal.
    } finally {
      setDownloading(false);
    }
  };

  const handlePatchWorld = async (relativePath: string) => {
    setPatchingPath(relativePath);
    try {
      await runTask<{ relative_path: string }>({
        action: "world_patch",
        relative_path: relativePath,
      });
      await refreshWorlds();
    } catch {
      // Displayed in terminal modal.
    } finally {
      setPatchingPath(null);
    }
  };

  const handleSyncProvider = async (providerKey: string) => {
    setSyncingProvider(providerKey);
    try {
      const next = await runTask<WorldsListResponse>({
        action: "world_provider_sync",
        provider: providerKey,
      });
      setData(next);
    } catch {
      // Displayed in terminal modal.
    } finally {
      setSyncingProvider(null);
    }
  };

  const handleRedownloadFuelWorld = async (
    item: WorldFileItem,
    scope: WorldScope,
  ) => {
    setRedownloadingPath(item.relative_path);
    try {
      const worldName = item.display_path.replace(/\.sdf$/i, "");
      const result = await runTask<{ relative_path: string }>({
        action: "world_download",
        world_name: worldName,
        select: false,
      });
      if (scope === "patched") {
        await runTask({
          action: "world_patch",
          relative_path: result.relative_path,
        });
      }
      await refreshWorlds();
    } catch {
      // Displayed in terminal modal.
    } finally {
      setRedownloadingPath(null);
    }
  };

  const handleSelectWorld = async (item: WorldFileItem) => {
    setError(null);
    setStatusMessage(null);
    try {
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          updates: {
            __SIM__ACTIVE_WORLD: {
              kind: "catalog",
              relative_path: item.relative_path,
            },
            __SIM__FUEL__WORLD_NAME: null,
            __SIM__FUEL__WORLD_URL: null,
          },
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      setStatusMessage(`Selected active world: catalog:${item.relative_path}`);
      await refreshWorlds();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleViewWorld = async (scope: WorldScope, relativePath: string) => {
    setInspectLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/worlds/${scope}/${encodeRelPath(relativePath)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      setInspected((await res.json()) as WorldReadResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setInspectLoading(false);
    }
  };

  const handleDeleteWorld = async (scope: WorldScope, relativePath: string) => {
    if (busy || !window.confirm(`Delete ${scope} world "${relativePath}"?`)) return;
    try {
      await runTask(
        {
          action: "world_delete",
          scope,
          relative_path: relativePath,
        },
        { openTerminal: false },
      );
      if (inspected?.scope === scope && inspected.relative_path === relativePath) {
        setInspected(null);
      }
      await refreshWorlds();
    } catch {
      // Displayed in terminal modal.
    }
  };

  const isWorldActive = (item: WorldFileItem): boolean => {
    const activeKey = data?.active.active_world_key ?? null;
    if (activeKey && activeKey === `catalog:${item.relative_path}`) {
      return true;
    }
    const wf = data?.active.world_file ?? null;
    if (wf && data) {
      return (
        wf === `${data.source_dir.replace(/\/+$/, "")}/${item.relative_path}` ||
        wf === `${data.patched_dir.replace(/\/+$/, "")}/${item.relative_path}` ||
        wf.endsWith(`/source_worlds/${item.relative_path}`) ||
        wf.endsWith(`/patched_worlds/${item.relative_path}`)
      );
    }
    return Boolean(
      data?.active.world_name &&
        item.provider === "fuel" &&
        item.name.replace(/\.sdf$/i, "") === data.active.world_name.split("/").pop(),
    );
  };

  const openWorldInfo = (
    item: WorldFileItem,
    provider: WorldProviderGroup,
    scope: WorldScope,
    isActive: boolean,
  ) => {
    const stage = scope === "patched" ? "Patched" : "Source";
    const rootDir = scope === "patched" ? data?.patched_dir ?? "" : data?.source_dir ?? "";
    const rootRel = scope === "patched" ? data?.patched_rel_dir : data?.source_rel_dir;
    const fullPath = `${rootDir.replace(/\/+$/, "")}/${item.relative_path}`;
    const rows: ItemInfoRow[] = [
      { label: "Name", value: item.name, mono: true },
      { label: "Origin", value: provider.label },
      { label: "Stage", value: stage },
      { label: "Relative Path", value: item.relative_path, mono: true, copyable: true },
      { label: "Full Path", value: fullPath, mono: true, copyable: true },
    ];
    if (rootRel) {
      rows.push({
        label: "Repo Path",
        value: `${rootRel.replace(/\/+$/, "")}/${item.relative_path}`,
        mono: true,
        copyable: true,
      });
    }
    rows.push(
      {
        label: "File Size",
        value: `${formatBytes(item.size_bytes)} (${item.size_bytes.toLocaleString()} bytes)`,
        mono: true,
      },
      { label: "Modified", value: new Date(item.modified_at).toLocaleString() },
      { label: "Patched", value: item.is_patched ? "Yes" : "No" },
      { label: "3D Mesh", value: item.has_3d === false ? "No" : "Yes" },
      { label: "Active", value: isActive ? "Yes" : "No" },
    );
    setInfoModal({
      title: item.display_path,
      subtitle: `${provider.label} · ${stage}`,
      rows,
    });
  };

  const providerList = data ? Object.values(data.providers) : [];
  const activeProvider =
    data?.providers[activeTab] ?? providerList[0] ?? null;

  const renderWorldSection = (
    provider: WorldProviderGroup,
    scope: WorldScope,
    items: WorldFileItem[],
  ) => {
    const isPatched = scope === "patched";
    const relDir = isPatched ? provider.patched_rel_dir : provider.source_rel_dir;
    const canDelete = isPatched || provider.can_delete_source;
    const title = isPatched
      ? `Patched ${provider.label} Worlds`
      : `Source ${provider.label} Worlds`;

    return (
      <section className="rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <div className="min-w-0">
            <h2 className="text-base font-semibold">
              {title} ({items.length})
            </h2>
            <code className="break-all text-xs text-zinc-500">{relDir}</code>
          </div>
          <span className="text-xs text-zinc-500">{items.length} file(s)</span>
        </header>
        <div className="p-4">
          {items.length > 0 ? (
            <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
              {items.map((item) => {
                const isActive = isWorldActive(item);
                const { dir, file } = splitRelPath(item.display_path);
                const folderPrefix = dir ? `${dir}/` : "./";
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
                      disabled={item.has_3d === false}
                      onClick={() =>
                        setPreviewTarget({ relativePath: item.relative_path, scope })
                      }
                      title={item.has_3d === false ? "No 3D mesh" : "Open 3D World Viewer"}
                      className="block w-full cursor-pointer text-left transition hover:opacity-90 disabled:cursor-default disabled:hover:opacity-100"
                    >
                      <WorldThumbnail
                        relativePath={item.relative_path}
                        scope={scope}
                        thumbnailUrl={item.thumbnail_url}
                      />
                    </button>
                    <div className="flex flex-1 flex-col justify-between gap-2 p-3">
                      <div>
                        <div
                          className="truncate font-mono text-[10px] text-zinc-500"
                          title={folderPrefix}
                        >
                          {folderPrefix}
                        </div>
                        <div className="flex items-center justify-between gap-1">
                          <span
                            className="truncate font-mono text-xs font-semibold"
                            title={item.relative_path}
                          >
                            {file}
                          </span>
                          {isActive && (
                            <span className="shrink-0 rounded bg-emerald-500/15 px-1.5 py-0.5 font-mono text-[10px] text-emerald-700 dark:text-emerald-300">
                              Active
                            </span>
                          )}
                        </div>
                        <div className="mt-0.5 font-mono text-[11px] text-zinc-500">
                          {formatBytes(item.size_bytes)}
                        </div>
                      </div>
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-1.5">
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
                            onClick={() => void handlePatchWorld(item.relative_path)}
                            disabled={busy || patchingPath !== null}
                            aria-label={isPatched || item.is_patched ? "Re-patch" : "Patch"}
                            title={
                              isPatched
                                ? "Re-patch"
                                : item.is_patched
                                  ? "Re-patch (Patched)"
                                  : "Patch (Not patched)"
                            }
                            className={`inline-flex items-center justify-center rounded border px-2 py-1 text-xs font-medium ${
                              busy
                                ? DISABLED_BUSY_BTN_CLASS
                                : !isPatched && !item.is_patched
                                  ? "border-amber-400 bg-amber-400 text-zinc-950 hover:bg-amber-300 disabled:opacity-50"
                                  : "border-zinc-300 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
                            }`}
                          >
                            <ToolsIcon />
                          </button>
                          {provider.supports_download && (
                            <button
                              type="button"
                              onClick={() => void handleRedownloadFuelWorld(item, scope)}
                              disabled={busy || redownloadingPath === item.relative_path}
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
                          )}
                          <button
                            type="button"
                            onClick={() => void handleViewWorld(scope, item.relative_path)}
                            disabled={inspectLoading}
                            aria-label="Inspect SDF"
                            title="Inspect SDF"
                            className="inline-flex flex-1 items-center justify-center rounded border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
                          >
                            <FileIcon />
                          </button>
                          <button
                            type="button"
                            onClick={() => openWorldInfo(item, provider, scope, isActive)}
                            aria-label="Info"
                            title="Info"
                            className="inline-flex items-center justify-center rounded border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
                          >
                            <InfoIcon />
                          </button>
                          {canDelete && (
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => void handleDeleteWorld(scope, item.relative_path)}
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
                        <button
                          type="button"
                          onClick={() => void handleSelectWorld(item)}
                          className="w-full rounded border border-zinc-300 px-2 py-1 text-center text-xs font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
                        >
                          Select
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="py-6 text-center text-xs text-zinc-500">
              {isPatched
                ? `No patched ${provider.label} worlds yet. Patch a world from Source ${provider.label} Worlds below.`
                : provider.supports_sync
                  ? `No ${provider.label} worlds found. Click "Sync ${provider.label} Worlds" above.`
                  : "No .sdf files found."}
            </div>
          )}
        </div>
      </section>
    );
  };

  return (
    <main className="mx-auto w-full max-w-6xl space-y-6 p-6 font-sans">
      <header className="space-y-3 border-b border-zinc-200 pb-4 dark:border-zinc-800">
        <div>
          <h1 className="text-2xl font-semibold">World Management</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Manage source &amp; patched worlds across providers, inspect SDF files, and select the active world
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => setShowJsonModal(true)}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            View JSON
          </button>
          <button
            type="button"
            onClick={() => void refreshWorlds()}
            disabled={loading}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </header>

      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          <p className="font-medium">World action failed</p>
          <p className="mt-1 break-all font-mono text-xs">{error}</p>
        </div>
      )}

      {statusMessage && (
        <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">
          {statusMessage}
        </div>
      )}

      {data && activeProvider && (
        <>
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
                {prov.label} Worlds ({prov.source_worlds.length})
              </button>
            ))}
          </div>

          <section className="grid gap-6 lg:grid-cols-12">
            <div
              className={`rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950 ${
                activeProvider.supports_download ? "lg:col-span-5" : "lg:col-span-12"
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-semibold">Active World</h2>
                {activeProvider.supports_sync && (
                  <button
                    type="button"
                    onClick={() => void handleSyncProvider(activeProvider.key)}
                    disabled={busy || syncingProvider === activeProvider.key}
                    className={`rounded-md border px-3 py-1 text-xs font-medium ${
                      busy
                        ? DISABLED_BUSY_BTN_CLASS
                        : "border-zinc-300 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
                    }`}
                  >
                    {syncingProvider === activeProvider.key
                      ? `Syncing ${activeProvider.label}...`
                      : `Sync ${activeProvider.label} Worlds`}
                  </button>
                )}
              </div>
              <dl className="mt-2 space-y-1.5 font-mono text-xs">
                {data.active.active_world_key && (
                  <div className="flex justify-between gap-2">
                    <dt className="text-zinc-500">active_world:</dt>
                    <dd className="break-all text-right font-semibold text-emerald-700 dark:text-emerald-300">
                      {data.active.active_world_key}
                    </dd>
                  </div>
                )}
                {data.active.world_file && (
                  <div className="flex justify-between gap-2">
                    <dt className="text-zinc-500">resolved_file:</dt>
                    <dd className="break-all text-right text-zinc-600 dark:text-zinc-400">
                      {data.active.world_file}
                    </dd>
                  </div>
                )}
                <div className="flex justify-between gap-2">
                  <dt className="text-zinc-500">world_name:</dt>
                  <dd className="break-all text-right">
                    {data.active.world_name ??
                      (data.active.world_file
                        ? "null (using world_file)"
                        : data.active.world_url
                          ? "null (using world_url)"
                          : "null (empty world)")}
                  </dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-zinc-500">world_url:</dt>
                  <dd className="break-all text-right">
                    {data.active.world_url ?? "null"}
                  </dd>
                </div>
              </dl>
            </div>

            {activeProvider.supports_download && (
              <form
                onSubmit={(e) => void handleDownload(e)}
                className="space-y-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950 lg:col-span-7"
              >
                <h2 className="text-sm font-semibold">Download from {activeProvider.label}</h2>
                <div className="grid gap-2 sm:grid-cols-2">
                  <input
                    type="text"
                    value={worldNameInput}
                    onChange={(e) => setWorldNameInput(e.target.value)}
                    placeholder="world_name (e.g. OpenRobotics/Urban Circuit 03)"
                    className="rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 font-mono text-xs outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
                  />
                  <input
                    type="text"
                    value={worldUrlInput}
                    onChange={(e) => setWorldUrlInput(e.target.value)}
                    placeholder="or world_url (https://app.gazebosim.org/...)"
                    className="rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 font-mono text-xs outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
                  />
                </div>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <label className="flex cursor-pointer items-center gap-2 text-xs text-zinc-600 dark:text-zinc-400">
                    <input
                      type="checkbox"
                      checked={selectOnDownload}
                      onChange={(e) => setSelectOnDownload(e.target.checked)}
                      className="h-4 w-4 accent-zinc-900 dark:accent-zinc-100"
                    />
                    <span>Save as active world in UI JSON</span>
                  </label>
                  <button
                    type="submit"
                    disabled={busy || downloading}
                    className={`rounded-md border px-3 py-1.5 text-xs font-medium ${
                      busy
                        ? DISABLED_BUSY_BTN_CLASS
                        : "border-transparent bg-zinc-900 text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
                    }`}
                  >
                    {downloading ? "Downloading..." : "Download"}
                  </button>
                </div>
              </form>
            )}
          </section>

          {renderWorldSection(activeProvider, "patched", activeProvider.patched_worlds)}
          {renderWorldSection(activeProvider, "source", activeProvider.source_worlds)}
        </>
      )}

      <SdfViewerModal
        open={inspectLoading || Boolean(inspected)}
        title={
          inspectLoading
            ? "Loading world SDF..."
            : `${inspected?.scope}/${inspected?.relative_path} (${inspected?.world_name ?? "unknown"} · ${formatBytes(inspected?.size_bytes ?? 0)})`
        }
        content={inspected?.content ?? null}
        loading={inspectLoading}
        onClose={() => setInspected(null)}
      />
      <WorldPreviewModal
        relativePath={previewTarget?.relativePath ?? null}
        scope={previewTarget?.scope ?? "patched"}
        onClose={() => setPreviewTarget(null)}
      />
      <UiJsonModal open={showJsonModal} onClose={() => setShowJsonModal(false)} />
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
