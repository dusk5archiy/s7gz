"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { SettingsGroupPanel } from "@/components/SettingsGroupPanel";
import { SettingsSidebar } from "@/components/SettingsSidebar";
import { UiJsonModal } from "@/components/UiJsonModal";
import { deepEqual, isFieldOverridden } from "@/lib/settings-utils";
import type {
  SettingsGroup,
  SettingsResponse,
  SettingsUpdateResponse,
} from "@/lib/types";

export default function Home() {
  const [groups, setGroups] = useState<SettingsGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [showJsonModal, setShowJsonModal] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [onlyOverridden, setOnlyOverridden] = useState(false);
  const [activeTab, setActiveTab] = useState<"fields" | "properties">("fields");
  const [drafts, setDrafts] = useState<Record<string, unknown>>({});

  const refreshSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/settings");
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      const data: SettingsResponse = await res.json();
      setGroups(data.groups);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/settings")
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${await res.text()}`);
        }
        return (await res.json()) as SettingsResponse;
      })
      .then((data) => {
        if (!cancelled) {
          setGroups(data.groups);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const fieldValueMap = useMemo(() => {
    const map = new Map<string, unknown>();
    for (const g of groups) {
      for (const f of g.fields) {
        map.set(f.env_key, f.value);
      }
    }
    return map;
  }, [groups]);

  const handleFieldChange = useCallback(
    (envKey: string, nextValue: unknown) => {
      setSaveSuccess(null);
      setDrafts((prev) => {
        const savedValue = fieldValueMap.get(envKey);
        if (deepEqual(nextValue, savedValue)) {
          if (!(envKey in prev)) return prev;
          const copy = { ...prev };
          delete copy[envKey];
          return copy;
        }
        return { ...prev, [envKey]: nextValue };
      });
    },
    [fieldValueMap],
  );

  const handleUndoField = useCallback((envKey: string) => {
    setDrafts((prev) => {
      if (!(envKey in prev)) return prev;
      const copy = { ...prev };
      delete copy[envKey];
      return copy;
    });
  }, []);

  const handleClearOverride = useCallback(async (envKey: string) => {
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(null);
    try {
      const res = await fetch(
        `/api/settings/overrides/${encodeURIComponent(envKey)}`,
        { method: "DELETE" },
      );
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      const data: SettingsUpdateResponse = await res.json();
      setGroups(data.groups);
      setDrafts((prev) => {
        if (!(envKey in prev)) return prev;
        const copy = { ...prev };
        delete copy[envKey];
        return copy;
      });
      setSaveSuccess(`Cleared UI override for ${envKey}.`);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }, []);

  const dirtyCount = Object.keys(drafts).length;

  const handleSave = useCallback(async () => {
    if (dirtyCount === 0) return;
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(null);
    try {
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ updates: drafts }),
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const errBody = (await res.json()) as { detail?: unknown };
          if (errBody.detail !== undefined) {
            detail = String(errBody.detail);
          }
        } catch {
          detail = `HTTP ${res.status}: ${await res.text()}`;
        }
        throw new Error(detail);
      }
      const data: SettingsUpdateResponse = await res.json();
      setGroups(data.groups);
      setDrafts({});
      setSaveSuccess(
        `Saved ${dirtyCount} change(s) to UI JSON (${Object.keys(data.saved).length} total keys).`,
      );
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }, [dirtyCount, drafts]);

  const visibleGroups = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return groups
      .filter((g) => selectedGroup === null || g.group === selectedGroup)
      .map((g) => {
        const groupMatches =
          q === "" ||
          g.group.toLowerCase().includes(q) ||
          g.prefix.toLowerCase().includes(q);
        const filteredFields = g.fields.filter((f) => {
          if (onlyOverridden && !isFieldOverridden(f)) return false;
          if (groupMatches) return true;
          return (
            f.name.toLowerCase().includes(q) ||
            f.env_key.toLowerCase().includes(q)
          );
        });
        return { ...g, fields: filteredFields };
      })
      .filter((g) => g.fields.length > 0);
  }, [groups, selectedGroup, searchQuery, onlyOverridden]);

  const propertyGroups = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return groups
      .filter((g) => (g.properties?.length ?? 0) > 0)
      .filter((g) => selectedGroup === null || g.group === selectedGroup)
      .map((g) => {
        const groupMatches =
          q === "" ||
          g.group.toLowerCase().includes(q) ||
          g.prefix.toLowerCase().includes(q);
        const props = (g.properties ?? []).filter(
          (p) => groupMatches || p.name.toLowerCase().includes(q),
        );
        return { ...g, properties: props };
      })
      .filter((g) => g.properties.length > 0);
  }, [groups, selectedGroup, searchQuery]);

  const totalPropertiesCount = useMemo(
    () => groups.reduce((sum, g) => sum + (g.properties?.length ?? 0), 0),
    [groups],
  );

  return (
    <main className="mx-auto w-full max-w-6xl p-6 font-sans">
      <header className="mb-6 space-y-3 border-b border-zinc-200 pb-4 dark:border-zinc-800">
        <div>
          <h1 className="text-2xl font-semibold">s7gz Settings</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Configure settings and save overrides to UI JSON
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {dirtyCount > 0 && (
            <>
              <span className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-800 dark:bg-blue-950 dark:text-blue-300">
                {dirtyCount} unsaved
              </span>
              <button
                type="button"
                onClick={() => {
                  setDrafts({});
                  setSaveError(null);
                }}
                disabled={saving}
                className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
              >
                Discard
              </button>
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={saving}
                className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                {saving ? "Saving..." : "Save to UI JSON"}
              </button>
            </>
          )}
          <button
            type="button"
            onClick={() => setShowJsonModal(true)}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            View JSON
          </button>
          <button
            type="button"
            onClick={() => void refreshSettings()}
            disabled={loading || saving}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          <p className="font-medium">Failed to load /api/settings</p>
          <p className="mt-1 font-mono text-xs">{error}</p>
        </div>
      )}

      {saveError && (
        <div className="mb-4 flex items-start justify-between gap-4 rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          <div>
            <p className="font-medium">Validation / Save Error</p>
            <p className="mt-1 break-all font-mono text-xs">{saveError}</p>
          </div>
          <button
            type="button"
            onClick={() => setSaveError(null)}
            className="shrink-0 text-xs underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {saveSuccess && (
        <div className="mb-4 flex items-center justify-between gap-4 rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">
          <span>{saveSuccess}</span>
          <button
            type="button"
            onClick={() => setSaveSuccess(null)}
            className="shrink-0 text-xs underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {!loading && !error && (
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
          <SettingsSidebar
            groups={groups}
            selectedGroup={selectedGroup}
            onSelectGroup={setSelectedGroup}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            onlyOverridden={onlyOverridden}
            onOnlyOverriddenChange={setOnlyOverridden}
          />

          <div className="min-w-0 flex-1 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 pb-2 dark:border-zinc-800">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveTab("fields")}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    activeTab === "fields"
                      ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                      : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
                  }`}
                >
                  Editable Fields
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("properties")}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    activeTab === "properties"
                      ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                      : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
                  }`}
                >
                  Computed Properties ({totalPropertiesCount})
                </button>
              </div>
            </div>

            {activeTab === "fields" ? (
              visibleGroups.length === 0 ? (
                <div className="rounded-lg border border-zinc-200 bg-white p-8 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950">
                  No matching settings found.
                </div>
              ) : (
                visibleGroups.map((g) => (
                  <SettingsGroupPanel
                    key={g.group}
                    group={g}
                    drafts={drafts}
                    onFieldChange={handleFieldChange}
                    onUndoField={handleUndoField}
                    onClearOverride={(envKey) => void handleClearOverride(envKey)}
                  />
                ))
              )
            ) : propertyGroups.length === 0 ? (
              <div className="rounded-lg border border-zinc-200 bg-white p-8 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950">
                No computed properties exposed for the current filter.
              </div>
            ) : (
              propertyGroups.map((g) => (
                <section
                  key={g.group}
                  className="rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950"
                >
                  <header className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
                    <div>
                      <h2 className="text-base font-semibold">{g.group}</h2>
                      {g.description && (
                        <p className="mt-0.5 text-xs text-zinc-500">
                          {g.description}
                        </p>
                      )}
                    </div>
                    <span className="text-xs text-zinc-500">
                      {g.properties.length} read-only
                    </span>
                  </header>
                  <div className="divide-y divide-zinc-100 dark:divide-zinc-900">
                    {g.properties.map((prop) => (
                      <div
                        key={prop.name}
                        className="grid gap-3 px-4 py-3 sm:grid-cols-12 sm:items-start"
                      >
                        <div className="min-w-0 space-y-1 sm:col-span-5">
                          <div className="font-mono text-sm font-medium">
                            {prop.name}
                          </div>
                          {prop.description && (
                            <p className="text-xs text-zinc-600 dark:text-zinc-400">
                              {prop.description}
                            </p>
                          )}
                        </div>
                        <div className="min-w-0 sm:col-span-7">
                          <div className="break-all rounded border border-zinc-200 bg-zinc-50 px-2.5 py-1.5 font-mono text-xs text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
                            {typeof prop.value === "string"
                              ? prop.value
                              : JSON.stringify(prop.value)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              ))
            )}
          </div>
        </div>
      )}
      <UiJsonModal open={showJsonModal} onClose={() => setShowJsonModal(false)} />
    </main>
  );
}
