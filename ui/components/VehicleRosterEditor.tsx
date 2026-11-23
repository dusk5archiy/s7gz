"use client";

import { Fragment, useState } from "react";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  CopyIcon,
  PasteIcon,
  PlusIcon,
  TrashIcon,
  XIcon,
} from "@/components/ActionIcons";
import { AssetRefPicker } from "@/components/AssetRefPicker";
import { FieldInput } from "@/components/FieldInput";
import { ModelPickerModal } from "@/components/ModelPickerModal";
import { assetRefsEqual, formatAssetRef } from "@/lib/asset-ref";
import type { RosterValidationResult } from "@/lib/validation";
import type {
  AssetRef,
  AttachmentCatalogItem,
  AttachmentSpec,
  BodyPose,
  DeviceCatalogItem,
  DeviceSpec,
  ScalarParamTuple,
  VehicleCatalogResponse,
  VehicleSpec,
} from "@/lib/types";

interface VehicleRosterEditorProps {
  catalog: VehicleCatalogResponse;
  vehicles: VehicleSpec[];
  savedVehicles?: VehicleSpec[];
  validation?: RosterValidationResult;
  onChange: (nextVehicles: VehicleSpec[]) => void;
}

function paramsToMap(params: ScalarParamTuple[]): Record<string, string | number | boolean> {
  const out: Record<string, string | number | boolean> = {};
  for (const [k, v] of params) {
    out[k] = v;
  }
  return out;
}

function mapToParams(map: Record<string, string | number | boolean>): ScalarParamTuple[] {
  return Object.entries(map);
}

/** Find the first unused `veh_N{i}` scanning from 0 upwards with step 1. */
function nextUniqueNamespace(existing: VehicleSpec[]): string {
  const used = new Set(existing.map((v) => v.namespace.trim()));
  let idx = 0;
  while (used.has(`veh_N${idx}`)) {
    idx += 1;
  }
  return `veh_N${idx}`;
}

function createBlankVehicle(existing: VehicleSpec[]): VehicleSpec {
  return {
    namespace: nextUniqueNamespace(existing),
    airframe: null,
    attachments: [],
    devices: [],
  };
}

function parseAssetRefJson(raw: unknown): AssetRef | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    return trimmed ? { kind: "path", path: trimmed } : null;
  }
  if (typeof raw === "object" && !Array.isArray(raw)) {
    const rec = raw as Record<string, unknown>;
    if (rec.kind === "catalog" && typeof rec.relative_path === "string") {
      return { kind: "catalog", relative_path: rec.relative_path };
    }
    if (rec.kind === "path" && typeof rec.path === "string") {
      return { kind: "path", path: rec.path };
    }
  }
  throw new Error("Invalid airframe object (expected { kind: 'catalog' | 'path', ... } or null)");
}

function parseBodyPoseJson(raw: unknown): BodyPose | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("pose_offset must be an object or null");
  }
  const r = raw as Record<string, unknown>;
  return {
    forward_m: Number(r.forward_m ?? 0),
    left_m: Number(r.left_m ?? 0),
    up_m: Number(r.up_m ?? 0),
    roll_rad: Number(r.roll_rad ?? 0),
    pitch_rad: Number(r.pitch_rad ?? 0),
    yaw_rad: Number(r.yaw_rad ?? 0),
  };
}

function parseParamsJson(raw: unknown): ScalarParamTuple[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((entry) => Array.isArray(entry) && entry.length >= 2)
    .map((entry) => [String(entry[0]), entry[1] as string | number | boolean]);
}

function parseVehicleJson(raw: unknown): Omit<VehicleSpec, "namespace"> & { namespace?: string } {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    throw new Error("Vehicle JSON must be an object");
  }
  const rec = raw as Record<string, unknown>;
  const attachments: AttachmentSpec[] = Array.isArray(rec.attachments)
    ? rec.attachments.map((item) => {
        if (typeof item !== "object" || item === null || Array.isArray(item)) {
          throw new Error("Attachment entry must be an object");
        }
        const a = item as Record<string, unknown>;
        return {
          slot: String(a.slot ?? ""),
          kind: String(a.kind ?? ""),
          pose_offset: parseBodyPoseJson(a.pose_offset),
          params: parseParamsJson(a.params),
        };
      })
    : [];
  const devices: DeviceSpec[] = Array.isArray(rec.devices)
    ? rec.devices.map((item) => {
        if (typeof item !== "object" || item === null || Array.isArray(item)) {
          throw new Error("Device entry must be an object");
        }
        const d = item as Record<string, unknown>;
        return {
          name: String(d.name ?? ""),
          kind: String(d.kind ?? ""),
          pose_offset: parseBodyPoseJson(d.pose_offset),
          params: parseParamsJson(d.params),
        };
      })
    : [];
  return {
    namespace: typeof rec.namespace === "string" ? rec.namespace.trim() : undefined,
    airframe: parseAssetRefJson(rec.airframe),
    attachments,
    devices,
  };
}

function InsertVehicleDivider({
  addLabel,
  pasteLabel,
  onAdd,
  onPaste,
}: {
  addLabel: string;
  pasteLabel: string;
  onAdd: () => void;
  onPaste: () => void;
}) {
  return (
    <div className="group relative flex items-center py-0.5">
      <div className="h-px flex-1 bg-zinc-200 transition-colors group-hover:bg-zinc-400 dark:bg-zinc-800 dark:group-hover:bg-zinc-600" />
      <div className="mx-2 flex shrink-0 items-center gap-1.5">
        <button
          type="button"
          onClick={onAdd}
          title={addLabel}
          aria-label={addLabel}
          className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-zinc-300 bg-white text-zinc-700 shadow-xs transition hover:border-zinc-900 hover:bg-zinc-900 hover:text-white dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:border-zinc-100 dark:hover:bg-zinc-100 dark:hover:text-zinc-900"
        >
          <PlusIcon className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={onPaste}
          title={pasteLabel}
          aria-label={pasteLabel}
          className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-zinc-300 bg-white text-zinc-700 shadow-xs transition hover:border-emerald-600 hover:bg-emerald-600 hover:text-white dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:border-emerald-500 dark:hover:bg-emerald-500 dark:hover:text-white"
        >
          <PasteIcon className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="h-px flex-1 bg-zinc-200 transition-colors group-hover:bg-zinc-400 dark:bg-zinc-800 dark:group-hover:bg-zinc-600" />
    </div>
  );
}

function PoseOffsetEditor({
  pose,
  defaultPose,
  onChange,
}: {
  pose: BodyPose | null;
  defaultPose: BodyPose;
  onChange: (next: BodyPose | null) => void;
}) {
  if (pose === null) {
    return (
      <div className="flex items-center justify-between text-xs text-zinc-500">
        <span>pose_offset: default</span>
        <button
          type="button"
          onClick={() => onChange({ ...defaultPose })}
          className="rounded border border-zinc-300 px-2 py-0.5 text-[11px] hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
        >
          Customize pose
        </button>
      </div>
    );
  }

  const keys: (keyof BodyPose)[] = [
    "forward_m",
    "left_m",
    "up_m",
    "roll_rad",
    "pitch_rad",
    "yaw_rad",
  ];

  return (
    <div className="space-y-1.5 rounded border border-zinc-200 p-2 dark:border-zinc-800">
      <div className="flex items-center justify-between text-[11px] text-zinc-500">
        <span className="font-mono">pose_offset (Body FLU)</span>
        <button
          type="button"
          onClick={() => onChange(null)}
          className="text-zinc-500 hover:underline"
        >
          Use default
        </button>
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        {keys.map((k) => (
          <label key={k} className="space-y-0.5 text-[11px]">
            <span className="block font-mono text-zinc-500">{k}</span>
            <input
              type="number"
              step="any"
              value={pose[k]}
              onChange={(e) => {
                const parsed = Number.parseFloat(e.target.value);
                if (Number.isFinite(parsed)) {
                  onChange({ ...pose, [k]: parsed });
                }
              }}
              className="w-full rounded border border-zinc-300 bg-white px-1.5 py-1 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-900"
            />
          </label>
        ))}
      </div>
    </div>
  );
}

export function VehicleRosterEditor({
  catalog,
  vehicles,
  savedVehicles = [],
  validation,
  onChange,
}: VehicleRosterEditorProps) {
  const [pickerVehicleIdx, setPickerVehicleIdx] = useState<number | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [pasteTarget, setPasteTarget] = useState<
    { mode: "insert"; index: number } | { mode: "replace"; index: number } | null
  >(null);
  const [pasteText, setPasteText] = useState("");
  const [pasteError, setPasteError] = useState<string | null>(null);

  const attachmentCatalogMap = new Map<string, AttachmentCatalogItem>(
    catalog.attachments.map((a) => [a.kind, a]),
  );
  const deviceCatalogMap = new Map<string, DeviceCatalogItem>(
    catalog.devices.map((d) => [d.kind, d]),
  );

  const updateVehicle = (index: number, next: VehicleSpec) => {
    const copy = [...vehicles];
    copy[index] = next;
    onChange(copy);
  };

  const insertBlankAt = (index: number) => {
    const next = [...vehicles];
    next.splice(index, 0, createBlankVehicle(vehicles));
    onChange(next);
  };

  const moveVehicle = (index: number, delta: -1 | 1) => {
    const target = index + delta;
    if (target < 0 || target >= vehicles.length) return;
    const copy = [...vehicles];
    const tmp = copy[index];
    copy[index] = copy[target];
    copy[target] = tmp;
    onChange(copy);
  };

  const handleCopyJson = async (key: string, payload: unknown) => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      setCopiedKey(key);
      window.setTimeout(() => {
        setCopiedKey((curr) => (curr === key ? null : curr));
      }, 1500);
    } catch {
      // Fallback: ignore if clipboard API unavailable
    }
  };

  const openPasteModal = async (
    target: { mode: "insert"; index: number } | { mode: "replace"; index: number },
  ) => {
    setPasteTarget(target);
    setPasteError(null);
    let initial = "";
    try {
      initial = await navigator.clipboard.readText();
    } catch {
      // Clipboard read may require permission; user can Ctrl+V manually
    }
    setPasteText(initial);
  };

  const handleApplyPaste = () => {
    if (!pasteTarget) return;
    setPasteError(null);
    try {
      const parsed: unknown = JSON.parse(pasteText);
      if (pasteTarget.mode === "replace") {
        const targetVehicle = vehicles[pasteTarget.index];
        if (!targetVehicle) return;
        const spec = parseVehicleJson(parsed);
        const otherNamespaces = new Set(
          vehicles
            .filter((_, i) => i !== pasteTarget.index)
            .map((v) => v.namespace.trim()),
        );
        const nextNs =
          spec.namespace && !otherNamespaces.has(spec.namespace)
            ? spec.namespace
            : targetVehicle.namespace;
        updateVehicle(pasteTarget.index, {
          namespace: nextNs,
          airframe: spec.airframe,
          attachments: spec.attachments,
          devices: spec.devices,
        });
      } else {
        const rawList = Array.isArray(parsed) ? parsed : [parsed];
        const nextRoster = [...vehicles];
        const toInsert: VehicleSpec[] = [];
        for (const item of rawList) {
          const spec = parseVehicleJson(item);
          const ns = nextUniqueNamespace([...nextRoster, ...toInsert]);
          toInsert.push({
            namespace: ns,
            airframe: spec.airframe,
            attachments: spec.attachments,
            devices: spec.devices,
          });
        }
        nextRoster.splice(pasteTarget.index, 0, ...toInsert);
        onChange(nextRoster);
      }
      setPasteTarget(null);
      setPasteText("");
    } catch (err) {
      setPasteError(err instanceof Error ? err.message : "Invalid JSON");
    }
  };

  return (
    <section className="space-y-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-zinc-200 bg-white px-4 py-2.5 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Vehicle Roster</h2>
          <span className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[11px] text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
            {vehicles.length}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            disabled={vehicles.length === 0}
            onClick={() => void handleCopyJson("roster", vehicles)}
            title="Copy entire vehicle roster as JSON"
            className="inline-flex items-center gap-1 rounded-md border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            <CopyIcon className="h-3.5 w-3.5" />
            <span>{copiedKey === "roster" ? "Copied!" : "Copy JSON"}</span>
          </button>
          <button
            type="button"
            onClick={() => void openPasteModal({ mode: "insert", index: vehicles.length })}
            title="Paste vehicle JSON (object or array) to append to roster"
            className="inline-flex items-center gap-1 rounded-md border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            <PasteIcon className="h-3.5 w-3.5" />
            <span>Paste JSON</span>
          </button>
        </div>
      </div>

      <InsertVehicleDivider
        addLabel={
          vehicles.length === 0
            ? "Add blank vehicle"
            : "Insert blank vehicle at top"
        }
        pasteLabel={
          vehicles.length === 0
            ? "Paste vehicle JSON"
            : "Paste vehicle JSON at top"
        }
        onAdd={() => insertBlankAt(0)}
        onPaste={() => void openPasteModal({ mode: "insert", index: 0 })}
      />

      {vehicles.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-300 bg-white p-6 text-center text-xs text-zinc-500 dark:border-zinc-700 dark:bg-zinc-950">
          Fleet is empty. Click <strong>+</strong> above to add a blank vehicle or click the{" "}
          <strong>Paste</strong> button to insert from JSON.
        </div>
      ) : (
        <div className="space-y-2.5">
          {vehicles.map((vehicle, vIdx) => (
            <Fragment key={vIdx}>
              <div className="space-y-4 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
                <header className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-100 pb-3 dark:border-zinc-900">
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-zinc-900 px-2 py-0.5 font-mono text-xs font-medium text-white dark:bg-zinc-100 dark:text-zinc-900">
                      #{vIdx}
                    </span>
                    <span className="font-mono text-sm font-semibold">
                      {vehicle.namespace || "(unnamed)"}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      disabled={vIdx === 0}
                      onClick={() => moveVehicle(vIdx, -1)}
                      title="Move vehicle up"
                      aria-label="Move vehicle up"
                      className="inline-flex h-7 w-7 items-center justify-center rounded border border-zinc-300 text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:border-zinc-400 disabled:bg-zinc-400 disabled:text-white dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:disabled:border-zinc-600 dark:disabled:bg-zinc-600 dark:disabled:text-white"
                    >
                      <ArrowUpIcon className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      disabled={vIdx === vehicles.length - 1}
                      onClick={() => moveVehicle(vIdx, 1)}
                      title="Move vehicle down"
                      aria-label="Move vehicle down"
                      className="inline-flex h-7 w-7 items-center justify-center rounded border border-zinc-300 text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:border-zinc-400 disabled:bg-zinc-400 disabled:text-white dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:disabled:border-zinc-600 dark:disabled:bg-zinc-600 dark:disabled:text-white"
                    >
                      <ArrowDownIcon className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleCopyJson(`veh-${vIdx}`, vehicle)}
                      title="Copy vehicle JSON"
                      className="inline-flex items-center gap-1 rounded border border-zinc-300 px-2 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                    >
                      <CopyIcon className="h-3.5 w-3.5" />
                      <span>{copiedKey === `veh-${vIdx}` ? "Copied" : "Copy"}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => void openPasteModal({ mode: "replace", index: vIdx })}
                      title="Paste vehicle JSON onto this vehicle"
                      className="inline-flex items-center gap-1 rounded border border-zinc-300 px-2 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                    >
                      <PasteIcon className="h-3.5 w-3.5" />
                      <span>Paste</span>
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        onChange(vehicles.filter((_, idx) => idx !== vIdx))
                      }
                      title="Remove vehicle"
                      aria-label="Remove vehicle"
                      className="inline-flex h-7 w-7 items-center justify-center rounded border border-rose-300 text-rose-600 hover:bg-rose-50 dark:border-rose-900/60 dark:text-rose-400 dark:hover:bg-rose-950/40"
                    >
                      <TrashIcon className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </header>

              <div className="space-y-3">
                <div className="space-y-1 text-xs">
                  <span className="block font-medium text-zinc-600 dark:text-zinc-400">
                    Airframe Model SDF *
                  </span>
                  {(() => {
                    const savedAirframe = savedVehicles[vIdx]?.airframe ?? null;
                    const currentAirframe = vehicle.airframe ?? null;
                    const canResetAirframe = !assetRefsEqual(currentAirframe, savedAirframe);
                    return (
                      <AssetRefPicker
                        value={currentAirframe}
                        canReset={canResetAirframe}
                        error={validation?.byIndex[vIdx]?.airframe ?? null}
                        catalogPlaceholder="px4/x500/model.sdf"
                        pathPlaceholder="runtime/... or /abs/path/model.sdf"
                        browseTitle="Browse model catalog"
                        resetTitle={
                          savedAirframe
                            ? `Reset airframe to saved (${formatAssetRef(savedAirframe)})`
                            : "Clear airframe"
                        }
                        onChange={(nextAirframe) =>
                          updateVehicle(vIdx, {
                            ...vehicle,
                            airframe: nextAirframe,
                          })
                        }
                        onOpenCatalog={() => setPickerVehicleIdx(vIdx)}
                        onReset={() =>
                          updateVehicle(vIdx, {
                            ...vehicle,
                            airframe: savedAirframe ? { ...savedAirframe } : null,
                          })
                        }
                      />
                    );
                  })()}
                </div>

                <label className="block space-y-1 text-xs">
                  <span className="block font-medium text-zinc-600 dark:text-zinc-400">
                    Namespace *
                  </span>
                  <input
                    type="text"
                    value={vehicle.namespace}
                    onChange={(e) =>
                      updateVehicle(vIdx, {
                        ...vehicle,
                        namespace: e.target.value,
                      })
                    }
                    className={`w-full rounded-md border bg-white px-2.5 py-1.5 font-mono text-xs dark:bg-zinc-900 ${
                      validation?.byIndex[vIdx]?.namespace
                        ? "border-rose-500 focus:border-rose-500"
                        : "border-zinc-300 dark:border-zinc-700"
                    }`}
                  />
                  {validation?.byIndex[vIdx]?.namespace && (
                    <span className="block text-[11px] text-rose-600 dark:text-rose-400">
                      {validation.byIndex[vIdx].namespace}
                    </span>
                  )}
                </label>
              </div>

              <div className="space-y-2 border-t border-zinc-100 pt-3 dark:border-zinc-900">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                    Attachments ({vehicle.attachments.length})
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {catalog.attachments.map((attMeta) => (
                      <button
                        key={attMeta.kind}
                        type="button"
                        onClick={() => {
                          const nextAtt: AttachmentSpec = {
                            slot: attMeta.default_slot,
                            kind: attMeta.kind,
                            pose_offset: null,
                            params: [],
                          };
                          updateVehicle(vIdx, {
                            ...vehicle,
                            attachments: [...vehicle.attachments, nextAtt],
                          });
                        }}
                        className="rounded border border-zinc-300 px-2 py-0.5 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
                      >
                        + {attMeta.kind}
                      </button>
                    ))}
                  </div>
                </div>

                {vehicle.attachments.map((att, aIdx) => {
                  const meta = attachmentCatalogMap.get(att.kind);
                  const paramMap = paramsToMap(att.params);
                  return (
                    <div
                      key={aIdx}
                      className="space-y-2 rounded-md border border-zinc-200 bg-zinc-50/50 p-3 dark:border-zinc-800 dark:bg-zinc-900/40"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="rounded bg-zinc-200 px-1.5 py-0.5 font-mono text-xs font-medium dark:bg-zinc-800">
                            {att.kind}
                          </span>
                          <input
                            type="text"
                            value={att.slot}
                            onChange={(e) => {
                              const nextAtts = [...vehicle.attachments];
                              nextAtts[aIdx] = { ...att, slot: e.target.value };
                              updateVehicle(vIdx, { ...vehicle, attachments: nextAtts });
                            }}
                            placeholder="slot"
                            className="w-32 rounded border border-zinc-300 bg-white px-2 py-0.5 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-900"
                          />
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            updateVehicle(vIdx, {
                              ...vehicle,
                              attachments: vehicle.attachments.filter(
                                (_, idx) => idx !== aIdx,
                              ),
                            })
                          }
                          className="text-xs text-red-600 hover:underline dark:text-red-400"
                        >
                          Remove
                        </button>
                      </div>

                      {meta && (
                        <>
                          <PoseOffsetEditor
                            pose={att.pose_offset}
                            defaultPose={meta.default_pose}
                            onChange={(nextPose) => {
                              const nextAtts = [...vehicle.attachments];
                              nextAtts[aIdx] = { ...att, pose_offset: nextPose };
                              updateVehicle(vIdx, { ...vehicle, attachments: nextAtts });
                            }}
                          />
                          <div className="grid gap-2 sm:grid-cols-2">
                            {meta.params_schema.map((p) => {
                              const val =
                                p.name in paramMap
                                  ? paramMap[p.name]
                                  : meta.default_params[p.name];
                              return (
                                <div key={p.name} className="space-y-0.5">
                                  <div className="font-mono text-[11px] text-zinc-500">
                                    {p.name}
                                  </div>
                                  <FieldInput
                                    envKey={`v${vIdx}-a${aIdx}-${p.name}`}
                                    schema={p.schema}
                                    value={val}
                                    onChange={(nextVal) => {
                                      const nextMap = { ...paramMap };
                                      if (nextVal === meta.default_params[p.name]) {
                                        delete nextMap[p.name];
                                      } else {
                                        nextMap[p.name] = nextVal as
                                          | string
                                          | number
                                          | boolean;
                                      }
                                      const nextAtts = [...vehicle.attachments];
                                      nextAtts[aIdx] = {
                                        ...att,
                                        params: mapToParams(nextMap),
                                      };
                                      updateVehicle(vIdx, {
                                        ...vehicle,
                                        attachments: nextAtts,
                                      });
                                    }}
                                  />
                                </div>
                              );
                            })}
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="space-y-2 border-t border-zinc-100 pt-3 dark:border-zinc-900">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                    Devices ({vehicle.devices.length})
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {catalog.devices.map((devMeta) => (
                      <button
                        key={devMeta.kind}
                        type="button"
                        onClick={() => {
                          const nextDev: DeviceSpec = {
                            name: devMeta.default_name,
                            kind: devMeta.kind,
                            pose_offset: null,
                            params: [],
                          };
                          updateVehicle(vIdx, {
                            ...vehicle,
                            devices: [...vehicle.devices, nextDev],
                          });
                        }}
                        className="rounded border border-zinc-300 px-2 py-0.5 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
                      >
                        + {devMeta.kind}
                      </button>
                    ))}
                  </div>
                </div>

                {vehicle.devices.map((dev, dIdx) => {
                  const meta = deviceCatalogMap.get(dev.kind);
                  const paramMap = paramsToMap(dev.params);
                  return (
                    <div
                      key={dIdx}
                      className="space-y-2 rounded-md border border-zinc-200 bg-zinc-50/50 p-3 dark:border-zinc-800 dark:bg-zinc-900/40"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="rounded bg-zinc-200 px-1.5 py-0.5 font-mono text-xs font-medium dark:bg-zinc-800">
                            {dev.kind}
                          </span>
                          <input
                            type="text"
                            value={dev.name}
                            onChange={(e) => {
                              const nextDevs = [...vehicle.devices];
                              nextDevs[dIdx] = { ...dev, name: e.target.value };
                              updateVehicle(vIdx, { ...vehicle, devices: nextDevs });
                            }}
                            placeholder="device name"
                            className="w-32 rounded border border-zinc-300 bg-white px-2 py-0.5 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-900"
                          />
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            updateVehicle(vIdx, {
                              ...vehicle,
                              devices: vehicle.devices.filter(
                                (_, idx) => idx !== dIdx,
                              ),
                            })
                          }
                          className="text-xs text-red-600 hover:underline dark:text-red-400"
                        >
                          Remove
                        </button>
                      </div>

                      {meta && (
                        <>
                          <PoseOffsetEditor
                            pose={dev.pose_offset}
                            defaultPose={meta.default_pose}
                            onChange={(nextPose) => {
                              const nextDevs = [...vehicle.devices];
                              nextDevs[dIdx] = { ...dev, pose_offset: nextPose };
                              updateVehicle(vIdx, { ...vehicle, devices: nextDevs });
                            }}
                          />
                          <div className="grid gap-2 sm:grid-cols-2">
                            {meta.params_schema.map((p) => {
                              const val =
                                p.name in paramMap
                                  ? paramMap[p.name]
                                  : meta.default_params[p.name];
                              return (
                                <div key={p.name} className="space-y-0.5">
                                  <div className="font-mono text-[11px] text-zinc-500">
                                    {p.name}
                                  </div>
                                  <FieldInput
                                    envKey={`v${vIdx}-d${dIdx}-${p.name}`}
                                    schema={p.schema}
                                    value={val}
                                    onChange={(nextVal) => {
                                      const nextMap = { ...paramMap };
                                      if (nextVal === meta.default_params[p.name]) {
                                        delete nextMap[p.name];
                                      } else {
                                        nextMap[p.name] = nextVal as
                                          | string
                                          | number
                                          | boolean;
                                      }
                                      const nextDevs = [...vehicle.devices];
                                      nextDevs[dIdx] = {
                                        ...dev,
                                        params: mapToParams(nextMap),
                                      };
                                      updateVehicle(vIdx, {
                                        ...vehicle,
                                        devices: nextDevs,
                                      });
                                    }}
                                  />
                                </div>
                              );
                            })}
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
              </div>
              <InsertVehicleDivider
                addLabel={
                  vIdx === vehicles.length - 1
                    ? "Add blank vehicle at bottom"
                    : `Insert blank vehicle after #${vIdx}`
                }
                pasteLabel={
                  vIdx === vehicles.length - 1
                    ? "Paste vehicle JSON at bottom"
                    : `Paste vehicle JSON after #${vIdx}`
                }
                onAdd={() => insertBlankAt(vIdx + 1)}
                onPaste={() => void openPasteModal({ mode: "insert", index: vIdx + 1 })}
              />
            </Fragment>
          ))}
        </div>
      )}

      <ModelPickerModal
        open={pickerVehicleIdx !== null}
        currentRelativePath={
          pickerVehicleIdx !== null &&
          vehicles[pickerVehicleIdx]?.airframe?.kind === "catalog"
            ? vehicles[pickerVehicleIdx].airframe.relative_path
            : ""
        }
        onSelect={(relativePath) => {
          if (pickerVehicleIdx !== null && vehicles[pickerVehicleIdx]) {
            updateVehicle(pickerVehicleIdx, {
              ...vehicles[pickerVehicleIdx],
              airframe: { kind: "catalog", relative_path: relativePath },
            });
          }
        }}
        onClose={() => setPickerVehicleIdx(null)}
      />

      {pasteTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
          onClick={() => setPasteTarget(null)}
        >
          <div
            className="flex w-full max-w-xl flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-950"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="flex items-center justify-between gap-2 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
              <div>
                <h3 className="text-sm font-semibold">
                  {pasteTarget.mode === "insert"
                    ? `Paste Vehicle JSON (Insert at #${pasteTarget.index})`
                    : `Paste Vehicle JSON onto #${pasteTarget.index}`}
                </h3>
                <p className="text-xs text-zinc-500">
                  {pasteTarget.mode === "insert"
                    ? "Paste a single vehicle object or an array of vehicles. Namespaces are auto-assigned."
                    : "Paste a vehicle object to overwrite airframe, attachments, and devices."}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPasteTarget(null)}
                aria-label="Close"
                className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-zinc-200 text-zinc-500 hover:bg-zinc-100 dark:border-zinc-800 dark:hover:bg-zinc-900"
              >
                <XIcon className="h-3.5 w-3.5" />
              </button>
            </header>
            <div className="space-y-2 p-4">
              <textarea
                rows={10}
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                placeholder='{"airframe": {"kind": "catalog", "relative_path": "px4/x500/model.sdf"}, "attachments": [], "devices": []}'
                className="w-full rounded-md border border-zinc-300 bg-zinc-50 p-2.5 font-mono text-xs outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
              />
              {pasteError && (
                <div className="rounded border border-rose-300 bg-rose-50 px-3 py-2 font-mono text-xs text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-300">
                  {pasteError}
                </div>
              )}
            </div>
            <footer className="flex items-center justify-end gap-2 border-t border-zinc-200 px-4 py-3 dark:border-zinc-800">
              <button
                type="button"
                onClick={() => setPasteTarget(null)}
                className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleApplyPaste}
                className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
              >
                Apply JSON
              </button>
            </footer>
          </div>
        </div>
      )}
    </section>
  );
}
