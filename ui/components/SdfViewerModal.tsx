"use client";

import { useEffect, useState } from "react";

interface SdfViewerModalProps {
  open: boolean;
  title: string;
  content: string | null;
  loading?: boolean;
  onClose: () => void;
}

export function SdfViewerModal({
  open,
  title,
  content,
  loading = false,
  onClose,
}: SdfViewerModalProps) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const handleCopy = () => {
    if (!content) return;
    void navigator.clipboard?.writeText(content).then(() => {
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
        className="flex h-[82vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950 text-slate-100 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b border-zinc-800 px-4 py-3">
          <span className="truncate font-mono text-sm font-semibold">{title}</span>
          <div className="flex items-center gap-2">
            {content && (
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
              aria-label="Close SDF viewer"
              className="flex h-8 w-8 items-center justify-center rounded-md border border-zinc-800 bg-zinc-900 font-mono text-sm text-slate-300 hover:border-zinc-600 hover:text-white"
            >
              ✕
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto bg-[#0b1017] p-4">
          {loading ? (
            <div className="flex h-full items-center justify-center font-mono text-xs text-sky-300">
              Loading SDF...
            </div>
          ) : (
            <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-zinc-200">
              {content ?? ""}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
