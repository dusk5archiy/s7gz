"use client";

import { useEffect, useState } from "react";
import { WorldViewport3D } from "@/components/WorldViewport3D";
import type { WorldSceneResponse } from "@/lib/types";

interface WorldPreviewModalProps {
  relativePath: string | null;
  scope?: "source" | "patched";
  onClose: () => void;
}

const EMPTY_MEMBERS: never[] = [];

export function WorldPreviewModal({
  relativePath,
  scope = "patched",
  onClose,
}: WorldPreviewModalProps) {
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
    void fetch(
      `/api/worlds/scene?scope=${scope}&relative_path=${encodeURIComponent(relativePath)}`,
    )
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
        return (await res.json()) as WorldSceneResponse;
      })
      .then((next) => {
        if (!cancelled) {
          setSceneData(next);
          setLoadedKey(requestKey);
          setError(null);
        }
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

  const loading = Boolean(requestKey && loadedKey !== requestKey);
  const activeScene = loadedKey === requestKey ? sceneData : null;

  if (!relativePath) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        className="flex h-[84vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-zinc-800 bg-[#070a0f] text-slate-100 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-semibold">{relativePath}</span>
            <span className="rounded bg-emerald-500/15 px-2 py-0.5 font-mono text-[11px] text-emerald-300">
              3D World Viewer
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close 3D world viewer"
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
              Loading world scene...
            </div>
          ) : (
            <WorldViewport3D
              sceneData={activeScene}
              members={EMPTY_MEMBERS}
              baseStation={activeScene?.base_station ?? null}
              effectiveCenter={null}
              className="flex h-full flex-col overflow-hidden bg-[#070a0f] text-slate-200"
            />
          )}
        </div>
      </div>
    </div>
  );
}
