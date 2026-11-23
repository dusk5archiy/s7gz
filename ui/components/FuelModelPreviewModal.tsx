"use client";

import { useEffect, useState } from "react";
import { WorldViewport3D } from "@/components/WorldViewport3D";
import type { WorldSceneResponse, WorldSceneVisual } from "@/lib/types";

interface FuelModelPreviewModalProps {
  relativePath: string | null;
  scope?: "source" | "patched";
  onClose: () => void;
}

const EMPTY_MEMBERS: never[] = [];

export function FuelModelPreviewModal({
  relativePath,
  scope = "source",
  onClose,
}: FuelModelPreviewModalProps) {
  const [sceneData, setSceneData] = useState<WorldSceneResponse | null>(null);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!relativePath) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [relativePath, onClose]);

  const requestKey = relativePath ? `${scope}:${relativePath}` : null;

  useEffect(() => {
    if (!relativePath || !requestKey) return;
    let cancelled = false;
    const encoded = relativePath.split("/").map(encodeURIComponent).join("/");
    void fetch(`/api/models/visuals/${encoded}?scope=${scope}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
        return (await res.json()) as { visuals?: WorldSceneVisual[] };
      })
      .then((payload) => {
        if (cancelled) return;
        const visuals = payload.visuals ?? [];
        setSceneData({
          source_world: relativePath,
          base_station: null,
          models: [
            {
              name: relativePath,
              is_base_station: false,
              pose: {
                east_m: 0,
                north_m: 0,
                up_m: 0,
                roll_deg: 0,
                pitch_deg: 0,
                yaw_deg: 0,
              },
              visuals,
            },
          ],
        });
        setLoadedKey(requestKey);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setLoadedKey(requestKey);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [relativePath, scope, requestKey]);

  if (!relativePath) return null;

  const loading = loadedKey !== requestKey;
  const activeScene = loadedKey === requestKey ? sceneData : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        className="flex h-[84vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-zinc-800 bg-[#070a0f] text-slate-100 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="truncate font-mono text-sm font-semibold">{relativePath}</span>
            <span className="rounded bg-emerald-500/15 px-2 py-0.5 font-mono text-[11px] text-emerald-300">
              3D Model Viewer
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close 3D model viewer"
            className="flex h-8 w-8 items-center justify-center rounded-md border border-zinc-800 bg-zinc-900 font-mono text-sm text-slate-300 hover:border-zinc-600 hover:text-white"
          >
            ✕
          </button>
        </div>

        <div className="relative min-h-0 flex-1">
          {error ? (
            <div className="flex h-full items-center justify-center p-6 text-center font-mono text-xs text-rose-300">
              {error}
            </div>
          ) : loading && !activeScene ? (
            <div className="flex h-full items-center justify-center font-mono text-xs text-sky-300">
              Loading 3D model...
            </div>
          ) : (
            <WorldViewport3D
              sceneData={activeScene}
              members={EMPTY_MEMBERS}
              baseStation={null}
              effectiveCenter={null}
              fitMode="object"
              className="flex h-full flex-col overflow-hidden bg-[#070a0f] text-slate-200"
            />
          )}
        </div>
      </div>
    </div>
  );
}
