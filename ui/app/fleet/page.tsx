"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AssetRefPicker } from "@/components/AssetRefPicker";
import { UiJsonModal } from "@/components/UiJsonModal";
import { VehicleRosterEditor } from "@/components/VehicleRosterEditor";
import { WorldPickerModal } from "@/components/WorldPickerModal";
import { WorldViewport3D } from "@/components/WorldViewport3D";
import { assetRefsEqual, assetRefToKey } from "@/lib/asset-ref";
import { deepEqual } from "@/lib/settings-utils";
import type {
  AssetRef,
  CenterConfig,
  FleetMember,
  FleetPreviewResponse,
  FormationConfig,
  GeoPose,
  SettingsGroup,
  SettingsResponse,
  SettingsUpdateResponse,
  VehicleCatalogResponse,
  VehicleSpec,
  WorldFleetConfig,
  WorldSceneResponse,
} from "@/lib/types";

const FLEET_WORLDS_ENV_KEY = "__SIM__FLEET__WORLDS";

const DEFAULT_FLEET_CONFIG: WorldFleetConfig = {
  enabled: true,
  formation: {
    kind: "line_abreast",
    spacing_m: 2.5,
    min_separation_m: 1.0,
  },
  center: {
    kind: "base_station",
    base_station_half_m: 1.5,
    gap_m: 3.0,
    front_east: 0.0,
    front_north: 1.0,
    offset_up_m: 0.3,
  },
  pose_overrides: {},
  vehicles: [],
};

function wrapDeg180(deg: number): number {
  let wrapped = (((deg + 180) % 360) + 360) % 360 - 180;
  if (Object.is(wrapped, -0)) wrapped = 0;
  return wrapped;
}

function rotateAndTranslateMembers(
  members: FleetMember[],
  prevCenter: GeoPose,
  nextCenter: GeoPose,
): FleetMember[] {
  const dE = nextCenter.east_m - prevCenter.east_m;
  const dN = nextCenter.north_m - prevCenter.north_m;
  const dU = nextCenter.up_m - prevCenter.up_m;
  const dYaw = wrapDeg180(nextCenter.yaw_deg - prevCenter.yaw_deg);
  const rad = (dYaw * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  return members.map((m) => {
    const relE = m.pose.east_m - prevCenter.east_m;
    const relN = m.pose.north_m - prevCenter.north_m;
    const rotE = relE * cos - relN * sin;
    const rotN = relE * sin + relN * cos;
    return {
      ...m,
      pose: {
        ...m.pose,
        east_m: Number((prevCenter.east_m + rotE + dE).toFixed(4)),
        north_m: Number((prevCenter.north_m + rotN + dN).toFixed(4)),
        up_m: Number((m.pose.up_m + dU).toFixed(4)),
        yaw_deg: Number(wrapDeg180(m.pose.yaw_deg + dYaw).toFixed(2)),
      },
    };
  });
}

function computeLocalMembers(
  cfg: WorldFleetConfig,
  center: GeoPose,
): FleetMember[] {
  if (!cfg.enabled || cfg.vehicles.length === 0) return [];
  const count = cfg.vehicles.length;
  const yawRad = (center.yaw_deg * Math.PI) / 180;
  const cos = Math.cos(yawRad);
  const sin = Math.sin(yawRad);

  return cfg.vehicles.map((vehicle, idx) => {
    let localE = 0;
    let localN = 0;
    if (cfg.formation.kind === "line_abreast") {
      const offset = (idx - (count - 1) / 2) * cfg.formation.spacing_m;
      localN = offset;
    } else if (cfg.formation.kind === "ring" && count > 1) {
      const angle = (2 * Math.PI * idx) / count;
      localE = cfg.formation.radius_m * Math.cos(angle);
      localN = cfg.formation.radius_m * Math.sin(angle);
    }
    const worldE = center.east_m + localE * cos - localN * sin;
    const worldN = center.north_m + localE * sin + localN * cos;
    const defaultPose: GeoPose = {
      east_m: Number(worldE.toFixed(4)),
      north_m: Number(worldN.toFixed(4)),
      up_m: Number(center.up_m.toFixed(4)),
      roll_deg: center.roll_deg,
      pitch_deg: center.pitch_deg,
      yaw_deg: center.yaw_deg,
    };
    const pose = cfg.pose_overrides[vehicle.namespace] ?? defaultPose;
    return { index: idx, vehicle, pose };
  });
}

function extractFleetWorldsMap(groups: SettingsGroup[]): Record<string, WorldFleetConfig> {
  for (const g of groups) {
    for (const f of g.fields) {
      if (f.env_key === FLEET_WORLDS_ENV_KEY && f.value && typeof f.value === "object") {
        return f.value as Record<string, WorldFleetConfig>;
      }
    }
  }
  return {};
}

export default function FleetPage() {
  const [selectedWorldRef, setSelectedWorldRef] = useState<AssetRef | null>(null);
  const [activeWorldRef, setActiveWorldRef] = useState<AssetRef | null>(null);
  const [selectedWorldKey, setSelectedWorldKey] = useState<string>("");
  const [activeWorldKey, setActiveWorldKey] = useState<string | null>(null);
  const [hasSavedFleet, setHasSavedFleet] = useState(false);
  const [savedConfig, setSavedConfig] = useState<WorldFleetConfig>(DEFAULT_FLEET_CONFIG);
  const [draftConfig, setDraftConfig] = useState<WorldFleetConfig>(DEFAULT_FLEET_CONFIG);
  const [defaultConfig, setDefaultConfig] = useState<WorldFleetConfig>(DEFAULT_FLEET_CONFIG);

  const [members, setMembers] = useState<FleetMember[]>([]);
  const [baseStation, setBaseStation] = useState<GeoPose | null>(null);
  const [effectiveCenter, setEffectiveCenter] = useState<GeoPose | null>(null);
  const [sourceWorld, setSourceWorld] = useState<string | null>(null);
  const [sceneData, setSceneData] = useState<WorldSceneResponse | null>(null);
  const [selectedTarget, setSelectedTarget] = useState<"anchor" | string | null>("anchor");
  const [allGroups, setAllGroups] = useState<SettingsGroup[]>([]);
  const [catalog, setCatalog] = useState<VehicleCatalogResponse | null>(null);

  const [loading, setLoading] = useState(true);
  const [switchingWorld, setSwitchingWorld] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [showJsonModal, setShowJsonModal] = useState(false);
  const [showWorldPicker, setShowWorldPicker] = useState(false);

  const savedWorldsMap = useMemo(() => extractFleetWorldsMap(allGroups), [allGroups]);

  const applyPreviewPayload = useCallback((fleetData: FleetPreviewResponse) => {
    setSelectedWorldRef(fleetData.world_ref ?? null);
    setActiveWorldRef(fleetData.active_world_ref ?? null);
    setSelectedWorldKey(fleetData.world_key ?? "");
    setActiveWorldKey(fleetData.active_world_key ?? null);
    setHasSavedFleet(fleetData.has_saved_fleet);
    setSavedConfig(fleetData.fleet_config);
    setDraftConfig(fleetData.fleet_config);
    setDefaultConfig(fleetData.default_fleet_config ?? DEFAULT_FLEET_CONFIG);
    setMembers(fleetData.members);
    setBaseStation(fleetData.base_station);
    setEffectiveCenter(fleetData.effective_center);
    setSourceWorld(fleetData.source_world);
  }, []);

  const loadForWorld = useCallback(
    async (worldKey?: string | null, opts?: { initial?: boolean }) => {
      if (opts?.initial) setLoading(true);
      else setSwitchingWorld(true);
      setError(null);
      const q = worldKey ? `?world_key=${encodeURIComponent(worldKey)}` : "";
      const sceneQuery = worldKey
        ? `?world_key=${encodeURIComponent(worldKey)}&exclude_fleet=true`
        : "?exclude_fleet=true";
      try {
        const [fleetRes, settingsRes, catalogRes, sceneRes] = await Promise.all([
          fetch(`/api/fleet/preview${q}`),
          fetch("/api/settings"),
          fetch("/api/vehicles/catalog"),
          fetch(`/api/worlds/scene${sceneQuery}`),
        ]);
        if (!fleetRes.ok) {
          throw new Error(`Fleet HTTP ${fleetRes.status}: ${await fleetRes.text()}`);
        }
        if (!settingsRes.ok) {
          throw new Error(`Settings HTTP ${settingsRes.status}: ${await settingsRes.text()}`);
        }
        if (!catalogRes.ok) {
          throw new Error(`Catalog HTTP ${catalogRes.status}: ${await catalogRes.text()}`);
        }
        const fleetData = (await fleetRes.json()) as FleetPreviewResponse;
        const settingsData = (await settingsRes.json()) as SettingsResponse;
        const catalogData = (await catalogRes.json()) as VehicleCatalogResponse;
        let nextScene: WorldSceneResponse | null = null;
        if (sceneRes.ok) {
          nextScene = (await sceneRes.json()) as WorldSceneResponse;
        }
        applyPreviewPayload(fleetData);
        setAllGroups(settingsData.groups);
        setCatalog(catalogData);
        setSceneData(nextScene);
        setSelectedTarget("anchor");
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (opts?.initial) setLoading(false);
        else setSwitchingWorld(false);
      }
    },
    [applyPreviewPayload],
  );

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetch("/api/fleet/preview"),
      fetch("/api/settings"),
      fetch("/api/vehicles/catalog"),
      fetch("/api/worlds/scene?exclude_fleet=true"),
    ])
      .then(async ([fleetRes, settingsRes, catalogRes, sceneRes]) => {
        if (!fleetRes.ok) {
          throw new Error(`Fleet HTTP ${fleetRes.status}: ${await fleetRes.text()}`);
        }
        if (!settingsRes.ok) {
          throw new Error(`Settings HTTP ${settingsRes.status}: ${await settingsRes.text()}`);
        }
        if (!catalogRes.ok) {
          throw new Error(`Catalog HTTP ${catalogRes.status}: ${await catalogRes.text()}`);
        }
        const fleetData = (await fleetRes.json()) as FleetPreviewResponse;
        const settingsData = (await settingsRes.json()) as SettingsResponse;
        const catalogData = (await catalogRes.json()) as VehicleCatalogResponse;
        const nextScene = sceneRes.ok
          ? ((await sceneRes.json()) as WorldSceneResponse)
          : null;
        return { fleetData, settingsData, catalogData, nextScene };
      })
      .then(({ fleetData, settingsData, catalogData, nextScene }) => {
        if (!cancelled) {
          applyPreviewPayload(fleetData);
          setAllGroups(settingsData.groups);
          setCatalog(catalogData);
          setSceneData(nextScene);
          setSelectedTarget("anchor");
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
  }, [applyPreviewPayload]);

  const isDirty = useMemo(
    () => !deepEqual(draftConfig, savedConfig),
    [draftConfig, savedConfig],
  );

  const updateDraftConfig = useCallback(
    (updater: (prev: WorldFleetConfig) => WorldFleetConfig) => {
      setStatusMessage(null);
      const prev = draftConfig;
      const next = updater(prev);
      setDraftConfig(next);
      if (effectiveCenter) {
        const nextCenter =
          next.center.kind === "absolute" ? next.center.pose : effectiveCenter;
        if (
          prev.center.kind === "absolute" &&
          next.center.kind === "absolute" &&
          !deepEqual(prev.center.pose, next.center.pose) &&
          deepEqual(prev.vehicles, next.vehicles) &&
          deepEqual(prev.formation, next.formation)
        ) {
          const prevPose = prev.center.pose;
          const nextPose = next.center.pose;
          setMembers((prevM) =>
            rotateAndTranslateMembers(prevM, prevPose, nextPose),
          );
          setEffectiveCenter(nextPose);
        } else {
          setEffectiveCenter(nextCenter);
          setMembers(computeLocalMembers(next, nextCenter));
        }
      }
    },
    [draftConfig, effectiveCenter],
  );

  const handleSelectWorldRef = useCallback(
    async (nextRef: AssetRef | null) => {
      if (isDirty && !window.confirm("Discard unsaved fleet changes for the current world?")) {
        return;
      }
      setStatusMessage(null);
      const nextKey = assetRefToKey(nextRef);
      await loadForWorld(nextKey);
    },
    [isDirty, loadForWorld],
  );

  const handleSetAsActiveWorld = useCallback(async () => {
    if (!selectedWorldRef || !selectedWorldKey) return;
    setSaving(true);
    setError(null);
    setStatusMessage(null);
    try {
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          updates: {
            __SIM__ACTIVE_WORLD: selectedWorldRef,
            __SIM__FUEL__WORLD_NAME: null,
            __SIM__FUEL__WORLD_URL: null,
          },
        }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      const data = (await res.json()) as SettingsUpdateResponse;
      setAllGroups(data.groups);
      setActiveWorldRef(selectedWorldRef);
      setActiveWorldKey(selectedWorldKey);
      setStatusMessage(`Set active world to ${selectedWorldKey}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }, [selectedWorldRef, selectedWorldKey]);

  const handleCenterPoseChange = useCallback(
    (nextPose: GeoPose) => {
      updateDraftConfig((prev) => ({
        ...prev,
        center: { kind: "absolute", pose: nextPose },
      }));
    },
    [updateDraftConfig],
  );

  const handleMemberPoseChange = useCallback(
    (namespace: string, nextPose: GeoPose) => {
      setStatusMessage(null);
      setMembers((prev) =>
        prev.map((m) => (m.vehicle.namespace === namespace ? { ...m, pose: nextPose } : m)),
      );
      setDraftConfig((prev) => ({
        ...prev,
        pose_overrides: {
          ...prev.pose_overrides,
          [namespace]: nextPose,
        },
      }));
    },
    [],
  );

  const handleClearMemberPose = useCallback(
    (namespace: string) => {
      updateDraftConfig((prev) => {
        const nextOverrides = { ...prev.pose_overrides };
        delete nextOverrides[namespace];
        return { ...prev, pose_overrides: nextOverrides };
      });
    },
    [updateDraftConfig],
  );

  const handleSaveAndRefresh = async () => {
    if (!selectedWorldKey) {
      setError("Select or enter a target world path before saving a fleet.");
      return;
    }
    setSaving(true);
    setError(null);
    setStatusMessage(null);
    try {
      const nextWorlds: Record<string, WorldFleetConfig> = {
        ...savedWorldsMap,
        [selectedWorldKey]: draftConfig,
      };
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          updates: { [FLEET_WORLDS_ENV_KEY]: nextWorlds },
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
        throw new Error(body?.detail ? String(body.detail) : `HTTP ${res.status}`);
      }
      const data = (await res.json()) as SettingsUpdateResponse;
      setAllGroups(data.groups);

      const fleetRes = await fetch(
        `/api/fleet/preview?world_key=${encodeURIComponent(selectedWorldKey)}`,
      );
      if (!fleetRes.ok) {
        throw new Error(`Fleet HTTP ${fleetRes.status}: ${await fleetRes.text()}`);
      }
      const fleetData = (await fleetRes.json()) as FleetPreviewResponse;
      applyPreviewPayload(fleetData);
      setStatusMessage(`Saved fleet for ${selectedWorldKey}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const handleClearWorldFleet = async () => {
    if (!selectedWorldKey || !hasSavedFleet) return;
    if (!window.confirm(`Remove saved fleet config for "${selectedWorldKey}" (reset to empty)?`)) {
      return;
    }
    setSaving(true);
    setError(null);
    setStatusMessage(null);
    try {
      const nextWorlds = { ...savedWorldsMap };
      delete nextWorlds[selectedWorldKey];
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          updates: { [FLEET_WORLDS_ENV_KEY]: nextWorlds },
        }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
      const data = (await res.json()) as SettingsUpdateResponse;
      setAllGroups(data.groups);
      const fleetRes = await fetch(
        `/api/fleet/preview?world_key=${encodeURIComponent(selectedWorldKey)}`,
      );
      if (fleetRes.ok) {
        applyPreviewPayload((await fleetRes.json()) as FleetPreviewResponse);
      }
      setStatusMessage(`Cleared saved fleet for ${selectedWorldKey} (reset to empty).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const handleResetPlacement = () => {
    updateDraftConfig((prev) => ({
      ...prev,
      center: defaultConfig.center,
      pose_overrides: {},
    }));
    setSelectedTarget("anchor");
    setStatusMessage("Reset fleet anchor & per-drone overrides to default (unsaved).");
  };

  const isViewingActiveWorld = Boolean(
    activeWorldRef && selectedWorldRef && assetRefsEqual(activeWorldRef, selectedWorldRef),
  );
  const canResetWorldPicker = Boolean(
    activeWorldRef && !assetRefsEqual(activeWorldRef, selectedWorldRef),
  );

  return (
    <main className="mx-auto w-full max-w-6xl space-y-6 p-6 font-sans">
      <header className="space-y-3 border-b border-zinc-200 pb-4 dark:border-zinc-800">
        <div>
          <h1 className="text-2xl font-semibold">Fleet &amp; Vehicle Loadout</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Configure a per-world vehicle roster, formation layout, and world anchor stored in UI JSON
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {isDirty && (
            <>
              <button
                type="button"
                onClick={() => {
                  setDraftConfig(savedConfig);
                  void loadForWorld(selectedWorldKey || null);
                }}
                disabled={saving}
                className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
              >
                Discard
              </button>
              <button
                type="button"
                onClick={() => void handleSaveAndRefresh()}
                disabled={saving || !selectedWorldKey}
                className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                {saving ? "Saving..." : "Save Fleet"}
              </button>
            </>
          )}
          {hasSavedFleet && (
            <button
              type="button"
              onClick={() => void handleClearWorldFleet()}
              disabled={saving}
              className="rounded-md border border-rose-300 px-3 py-1.5 text-sm font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50 dark:border-rose-900/60 dark:text-rose-400 dark:hover:bg-rose-950/40"
            >
              Clear World Fleet
            </button>
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
            onClick={() => void loadForWorld(selectedWorldKey || null)}
            disabled={loading || switchingWorld || saving}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            {loading || switchingWorld ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </header>

      <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold">Target World</h2>
            {isViewingActiveWorld ? (
              <span className="rounded bg-emerald-500/15 px-2 py-0.5 font-mono text-[10px] text-emerald-700 dark:text-emerald-300">
                Active World
              </span>
            ) : selectedWorldKey ? (
              <span className="rounded bg-amber-500/15 px-2 py-0.5 font-mono text-[10px] text-amber-700 dark:text-amber-300">
                Non-Active World
              </span>
            ) : null}
            {selectedWorldKey && (
              <span
                className={`rounded px-2 py-0.5 font-mono text-[10px] ${
                  hasSavedFleet
                    ? "bg-sky-500/15 text-sky-700 dark:text-sky-300"
                    : "bg-zinc-100 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400"
                }`}
              >
                {hasSavedFleet ? "Fleet Saved in UI JSON" : "No Saved Fleet (Empty Default)"}
              </span>
            )}
          </div>
          {selectedWorldKey && !isViewingActiveWorld && (
            <button
              type="button"
              disabled={saving}
              onClick={() => void handleSetAsActiveWorld()}
              className="rounded-md border border-emerald-500/50 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-500/20 disabled:opacity-50 dark:text-emerald-300"
            >
              Set as Active World
            </button>
          )}
        </div>
        <AssetRefPicker
          value={selectedWorldRef}
          canReset={canResetWorldPicker}
          disabled={loading || switchingWorld || saving}
          catalogPlaceholder="Select world from catalog..."
          pathPlaceholder="runtime/... or /opt/ros/.../empty.sdf"
          browseTitle="Browse world catalog"
          resetTitle={
            activeWorldKey ? `Reset to active world (${activeWorldKey})` : "Nothing to reset"
          }
          onChange={(nextRef) => void handleSelectWorldRef(nextRef)}
          onOpenCatalog={() => setShowWorldPicker(true)}
          onReset={() => {
            if (activeWorldRef) {
              void handleSelectWorldRef(activeWorldRef);
            }
          }}
        />
      </section>

      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          <p className="font-medium">Fleet error</p>
          <p className="mt-1 break-all font-mono text-xs">{error}</p>
        </div>
      )}

      {statusMessage && (
        <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">
          {statusMessage}
        </div>
      )}

      {!loading && (
        <div className="grid gap-6 lg:grid-cols-12 lg:items-start">
          <div className="space-y-6 lg:col-span-7">
            {catalog && (
              <VehicleRosterEditor
                catalog={catalog}
                vehicles={draftConfig.vehicles}
                savedVehicles={savedConfig.vehicles}
                onChange={(nextVehicles: VehicleSpec[]) =>
                  updateDraftConfig((prev) => ({
                    ...prev,
                    vehicles: nextVehicles,
                  }))
                }
              />
            )}

            <section className="rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
              <header className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
                <div>
                  <h2 className="text-sm font-semibold">World Fleet Formation &amp; Anchor</h2>
                  <p className="text-xs text-zinc-500">
                    Saved under __SIM__FLEET__WORLDS[{selectedWorldKey || "..."}]
                  </p>
                </div>
                <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-medium">
                  <input
                    type="checkbox"
                    checked={draftConfig.enabled}
                    onChange={(e) =>
                      updateDraftConfig((prev) => ({ ...prev, enabled: e.target.checked }))
                    }
                    className="h-4 w-4 rounded border-zinc-300"
                  />
                  <span>Enabled</span>
                </label>
              </header>

              <div className="space-y-4 p-4 text-xs">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium text-zinc-700 dark:text-zinc-300">
                      Formation Layout
                    </span>
                    <div className="inline-flex rounded-md border border-zinc-200 p-0.5 dark:border-zinc-800">
                      {(["line_abreast", "ring"] as const).map((kind) => (
                        <button
                          key={kind}
                          type="button"
                          onClick={() =>
                            updateDraftConfig((prev) => {
                              if (prev.formation.kind === kind) return prev;
                              const nextFormation: FormationConfig =
                                kind === "line_abreast"
                                  ? {
                                      kind: "line_abreast",
                                      spacing_m: 2.5,
                                      min_separation_m: prev.formation.min_separation_m,
                                    }
                                  : {
                                      kind: "ring",
                                      radius_m: 3.0,
                                      min_separation_m: prev.formation.min_separation_m,
                                    };
                              return { ...prev, formation: nextFormation };
                            })
                          }
                          className={`rounded px-2.5 py-1 font-mono text-[11px] transition ${
                            draftConfig.formation.kind === kind
                              ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                              : "text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
                          }`}
                        >
                          {kind}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    {draftConfig.formation.kind === "line_abreast" ? (
                      <label className="space-y-1">
                        <span className="block text-zinc-500">spacing_m</span>
                        <input
                          type="number"
                          step="0.25"
                          min="0.1"
                          value={draftConfig.formation.spacing_m}
                          onChange={(e) => {
                            const val = Number.parseFloat(e.target.value);
                            if (!Number.isFinite(val) || val <= 0) return;
                            updateDraftConfig((prev) =>
                              prev.formation.kind === "line_abreast"
                                ? {
                                    ...prev,
                                    formation: { ...prev.formation, spacing_m: val },
                                  }
                                : prev,
                            );
                          }}
                          className="w-full rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-900"
                        />
                      </label>
                    ) : (
                      <label className="space-y-1">
                        <span className="block text-zinc-500">radius_m</span>
                        <input
                          type="number"
                          step="0.25"
                          min="0.1"
                          value={draftConfig.formation.radius_m}
                          onChange={(e) => {
                            const val = Number.parseFloat(e.target.value);
                            if (!Number.isFinite(val) || val <= 0) return;
                            updateDraftConfig((prev) =>
                              prev.formation.kind === "ring"
                                ? {
                                    ...prev,
                                    formation: { ...prev.formation, radius_m: val },
                                  }
                                : prev,
                            );
                          }}
                          className="w-full rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-900"
                        />
                      </label>
                    )}

                    <label className="space-y-1">
                      <span className="block text-zinc-500">min_separation_m</span>
                      <input
                        type="number"
                        step="0.1"
                        min="0.1"
                        value={draftConfig.formation.min_separation_m}
                        onChange={(e) => {
                          const val = Number.parseFloat(e.target.value);
                          if (!Number.isFinite(val) || val <= 0) return;
                          updateDraftConfig((prev) => ({
                            ...prev,
                            formation: { ...prev.formation, min_separation_m: val },
                          }));
                        }}
                        className="w-full rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-900"
                      />
                    </label>
                  </div>
                </div>

                <div className="space-y-2 border-t border-zinc-100 pt-3 dark:border-zinc-900">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium text-zinc-700 dark:text-zinc-300">
                      Center Anchor Mode
                    </span>
                    <div className="inline-flex rounded-md border border-zinc-200 p-0.5 dark:border-zinc-800">
                      {(["base_station", "absolute"] as const).map((kind) => (
                        <button
                          key={kind}
                          type="button"
                          onClick={() =>
                            updateDraftConfig((prev) => {
                              if (prev.center.kind === kind) return prev;
                              const nextCenter: CenterConfig =
                                kind === "base_station"
                                  ? {
                                      kind: "base_station",
                                      base_station_half_m: 1.5,
                                      gap_m: 3.0,
                                      front_east: 0.0,
                                      front_north: 1.0,
                                      offset_up_m: 0.3,
                                    }
                                  : {
                                      kind: "absolute",
                                      pose: effectiveCenter
                                        ? { ...effectiveCenter }
                                        : {
                                            east_m: 0,
                                            north_m: 0,
                                            up_m: 0.3,
                                            roll_deg: 0,
                                            pitch_deg: 0,
                                            yaw_deg: 0,
                                          },
                                    };
                              return { ...prev, center: nextCenter };
                            })
                          }
                          className={`rounded px-2.5 py-1 font-mono text-[11px] transition ${
                            draftConfig.center.kind === kind
                              ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                              : "text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
                          }`}
                        >
                          {kind}
                        </button>
                      ))}
                    </div>
                  </div>

                  {draftConfig.center.kind === "base_station" && (
                    <div className="grid gap-2 sm:grid-cols-3">
                      {(
                        [
                          ["base_station_half_m", draftConfig.center.base_station_half_m],
                          ["gap_m", draftConfig.center.gap_m],
                          ["offset_up_m", draftConfig.center.offset_up_m],
                        ] as const
                      ).map(([fieldKey, val]) => (
                        <label key={fieldKey} className="space-y-1">
                          <span className="block font-mono text-[11px] text-zinc-500">
                            {fieldKey}
                          </span>
                          <input
                            type="number"
                            step="0.25"
                            value={val}
                            onChange={(e) => {
                              const num = Number.parseFloat(e.target.value);
                              if (!Number.isFinite(num)) return;
                              updateDraftConfig((prev) =>
                                prev.center.kind === "base_station"
                                  ? {
                                      ...prev,
                                      center: { ...prev.center, [fieldKey]: num },
                                    }
                                  : prev,
                              );
                            }}
                            className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-900"
                          />
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </section>
          </div>

          <div className="space-y-4 lg:col-span-5">
            <section className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
              <h2 className="text-sm font-semibold">World Anchor &amp; Center</h2>
              <dl className="mt-2 space-y-1.5 font-mono text-xs">
                <div className="flex justify-between gap-2">
                  <dt className="text-zinc-500">source_world:</dt>
                  <dd className="break-all text-right">
                    {sourceWorld ?? "none (fallback origin)"}
                  </dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-zinc-500">base_station:</dt>
                  <dd className="break-all text-right">
                    {baseStation
                      ? `E=${baseStation.east_m.toFixed(2)}, N=${baseStation.north_m.toFixed(2)}, U=${baseStation.up_m.toFixed(2)}, yaw=${baseStation.yaw_deg.toFixed(1)}°`
                      : "not found"}
                  </dd>
                </div>
                {effectiveCenter && (
                  <div className="flex justify-between gap-2">
                    <dt className="text-zinc-500">effective_center:</dt>
                    <dd className="break-all text-right text-emerald-700 dark:text-emerald-400">
                      E={effectiveCenter.east_m.toFixed(2)}, N={effectiveCenter.north_m.toFixed(2)}, U={effectiveCenter.up_m.toFixed(2)}, yaw={effectiveCenter.yaw_deg.toFixed(1)}°
                    </dd>
                  </div>
                )}
              </dl>
            </section>

            <WorldViewport3D
              sceneData={sceneData}
              members={members}
              baseStation={baseStation}
              effectiveCenter={effectiveCenter}
              selectedTarget={selectedTarget}
              onSelectTarget={setSelectedTarget}
              onCenterChange={handleCenterPoseChange}
              onMemberPoseChange={handleMemberPoseChange}
            />

            {effectiveCenter && (
              <section
                onClick={() => setSelectedTarget("anchor")}
                className={`cursor-pointer rounded-lg border p-4 transition ${
                  selectedTarget === "anchor"
                    ? "border-orange-500 bg-orange-50/40 dark:border-orange-500/70 dark:bg-orange-950/20"
                    : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950"
                }`}
              >
                <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <h2 className="text-sm font-semibold">Fleet Anchor</h2>
                    <span className="rounded bg-orange-500/15 px-2 py-0.5 font-mono text-[10px] text-orange-600 dark:text-orange-300">
                      {selectedTarget === "anchor" ? "Gizmo: Active" : "Click to select"}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {draftConfig.center.kind === "absolute" ? (
                      <>
                        <span className="rounded bg-sky-500/20 px-1.5 py-0.5 font-mono text-[10px] text-sky-600 dark:text-sky-300">
                          Custom
                        </span>
                        <button
                          type="button"
                          disabled={saving}
                          onClick={(e) => {
                            e.stopPropagation();
                            updateDraftConfig((prev) => ({
                              ...prev,
                              center: defaultConfig.center,
                            }));
                          }}
                          title="Reset fleet anchor to default (base_station + standoff)"
                          className="rounded border border-zinc-300 px-2 py-0.5 text-[11px] font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                        >
                          Reset
                        </button>
                      </>
                    ) : (
                      <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 font-mono text-[10px] text-emerald-700 dark:text-emerald-300">
                        Default
                      </span>
                    )}
                  </div>
                </div>
                <div
                  className="grid grid-cols-4 gap-2 text-xs"
                  onClick={(e) => e.stopPropagation()}
                >
                  {(
                    [
                      ["East", "east_m", effectiveCenter.east_m],
                      ["North", "north_m", effectiveCenter.north_m],
                      ["Up", "up_m", effectiveCenter.up_m],
                      ["Yaw°", "yaw_deg", effectiveCenter.yaw_deg],
                    ] as const
                  ).map(([lbl, key, val]) => (
                    <label key={key} className="block">
                      <span className="block text-[10px] text-zinc-500">{lbl}</span>
                      <input
                        type="number"
                        step={key === "yaw_deg" ? 5 : 0.25}
                        value={Number(val.toFixed(3))}
                        onChange={(e) => {
                          const num = Number(e.target.value);
                          if (!Number.isFinite(num)) return;
                          handleCenterPoseChange({ ...effectiveCenter, [key]: num });
                        }}
                        className="mt-0.5 w-full rounded border border-zinc-300 bg-white px-1.5 py-1 font-mono text-[11px] dark:border-zinc-700 dark:bg-zinc-900"
                      />
                    </label>
                  ))}
                </div>
              </section>
            )}

            <section className="rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
              <header className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-semibold">Fleet Members</h2>
                  <span className="text-xs text-zinc-500">
                    {members.length} vehicle(s)
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={selectedTarget === null}
                    onClick={() => setSelectedTarget(null)}
                    className="rounded-md border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:border-zinc-400 disabled:bg-zinc-400 disabled:text-white dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900 dark:disabled:border-zinc-600 dark:disabled:bg-zinc-600 dark:disabled:text-white"
                  >
                    Deselect
                  </button>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={handleResetPlacement}
                    title="Clear center & per-drone overrides and reset fleet placement to default"
                    className="rounded-md border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                  >
                    Reset
                  </button>
                </div>
              </header>
              <div className="divide-y divide-zinc-100 dark:divide-zinc-900">
                {members.length === 0 && (
                  <div className="px-4 py-6 text-center text-xs text-zinc-500">
                    No vehicles configured for this world. Add a vehicle above and save to persist.
                  </div>
                )}
                {members.map((m) => {
                  const ns = m.vehicle.namespace;
                  const isSelected = selectedTarget === ns;
                  const isOverridden = ns in draftConfig.pose_overrides;
                  return (
                    <div
                      key={m.index}
                      onClick={() => setSelectedTarget(ns)}
                      className={`cursor-pointer space-y-2 px-4 py-3 text-xs transition ${
                        isSelected
                          ? "bg-orange-50/40 ring-1 ring-inset ring-orange-500 dark:bg-orange-950/20 dark:ring-orange-500/70"
                          : "hover:bg-zinc-50 dark:hover:bg-zinc-900/40"
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-sm font-semibold">
                            #{m.index} {m.vehicle.namespace}
                          </span>
                          {m.gz_model_name && (
                            <span className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[10px] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                              {m.gz_model_name}
                            </span>
                          )}
                          {isSelected && (
                            <span className="rounded bg-orange-500/15 px-2 py-0.5 font-mono text-[10px] text-orange-600 dark:text-orange-300">
                              Gizmo: Active
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5">
                          {isOverridden ? (
                            <>
                              <span className="rounded bg-sky-500/20 px-1.5 py-0.5 font-mono text-[10px] text-sky-600 dark:text-sky-300">
                                Custom
                              </span>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleClearMemberPose(ns);
                                }}
                                title="Khôi phục theo công thức đội hình"
                                className="rounded border border-zinc-300 px-1.5 py-0.5 text-[10px] hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
                              >
                                Reset
                              </button>
                            </>
                          ) : (
                            <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 font-mono text-[10px] text-emerald-700 dark:text-emerald-300">
                              Formation
                            </span>
                          )}
                        </div>
                      </div>
                      <div
                        className="grid grid-cols-4 gap-2"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {(
                          [
                            ["East", "east_m", m.pose.east_m],
                            ["North", "north_m", m.pose.north_m],
                            ["Up", "up_m", m.pose.up_m],
                            ["Yaw°", "yaw_deg", m.pose.yaw_deg],
                          ] as const
                        ).map(([lbl, key, val]) => (
                          <label key={key} className="block">
                            <span className="block text-[10px] text-zinc-500">{lbl}</span>
                            <input
                              type="number"
                              step={key === "yaw_deg" ? 5 : 0.25}
                              value={Number(val.toFixed(3))}
                              onChange={(e) => {
                                const num = Number(e.target.value);
                                if (!Number.isFinite(num)) return;
                                handleMemberPoseChange(ns, { ...m.pose, [key]: num });
                              }}
                              className="mt-0.5 w-full rounded border border-zinc-300 bg-white px-1.5 py-1 font-mono text-[11px] dark:border-zinc-700 dark:bg-zinc-900"
                            />
                          </label>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          </div>
        </div>
      )}

      <WorldPickerModal
        open={showWorldPicker}
        currentRelativePath={
          selectedWorldRef?.kind === "catalog" ? selectedWorldRef.relative_path : ""
        }
        onSelect={(relativePath) =>
          void handleSelectWorldRef({ kind: "catalog", relative_path: relativePath })
        }
        onClose={() => setShowWorldPicker(false)}
      />
      <UiJsonModal open={showJsonModal} onClose={() => setShowJsonModal(false)} />
    </main>
  );
}
