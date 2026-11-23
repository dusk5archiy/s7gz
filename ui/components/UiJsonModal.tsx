"use client";

import { useEffect, useState } from "react";

interface UiJsonModalProps {
  open: boolean;
  onClose: () => void;
}

interface OverridesResponse {
  path: string;
  overrides: Record<string, unknown>;
}

export function UiJsonModal({ open, onClose }: UiJsonModalProps) {
  const [data, setData] = useState<OverridesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("/api/settings/overrides");
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
        const json = (await res.json()) as OverridesResponse;
        if (!cancelled) setData(json);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  const formatted = data ? JSON.stringify(data.overrides, null, 2) : "";
  const keyCount = data ? Object.keys(data.overrides).length : 0;

  const handleCopy = () => {
    if (!formatted) return;
    void navigator.clipboard?.writeText(formatted).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        className="flex h-[78vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950 text-slate-100 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b border-zinc-800 px-4 py-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="truncate font-mono text-sm font-semibold">UI Overrides JSON</span>
              {data && (
                <span className="shrink-0 rounded bg-sky-500/15 px-2 py-0.5 font-mono text-[11px] text-sky-300">
                  {keyCount} key(s)
                </span>
              )}
            </div>
            {data?.path && (
              <div className="mt-0.5 truncate font-mono text-[11px] text-zinc-400">
                {data.path}
              </div>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {formatted && (
              <button
                type="button"
                onClick={handleCopy}
                className="rounded-md border border-zinc-700 bg-zinc-900 px-2.5 py-1 text-xs text-slate-300 hover:border-zinc-500 hover:text-white"
              >
                {copied ? "Copied" : "Copy"}
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close JSON viewer"
              className="flex h-8 w-8 items-center justify-center rounded-md border border-zinc-800 bg-zinc-900 font-mono text-sm text-slate-300 hover:border-zinc-600 hover:text-white"
            >
              ✕
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto bg-[#0b1017] p-4">
          {loading ? (
            <div className="flex h-full items-center justify-center font-mono text-xs text-sky-300">
              Loading UI JSON...
            </div>
          ) : error ? (
            <div className="font-mono text-xs text-rose-400">{error}</div>
          ) : (
            <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-zinc-200">
              {formatted}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
