"use client";

import { useEffect, useState } from "react";

export interface ItemInfoRow {
  label: string;
  value: string;
  mono?: boolean;
  copyable?: boolean;
}

interface ItemInfoModalProps {
  open: boolean;
  title: string;
  subtitle?: string;
  rows: ItemInfoRow[];
  onClose: () => void;
}

export function ItemInfoModal({
  open,
  title,
  subtitle,
  rows,
  onClose,
}: ItemInfoModalProps) {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const handleCopy = (label: string, value: string) => {
    void navigator.clipboard?.writeText(value).then(() => {
      setCopiedKey(label);
      window.setTimeout(() => {
        setCopiedKey((prev) => (prev === label ? null : prev));
      }, 1500);
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        className="flex max-h-[82vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950 text-slate-100 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b border-zinc-800 px-4 py-3">
          <div className="min-w-0">
            <h3 className="truncate font-mono text-sm font-semibold">{title}</h3>
            {subtitle && (
              <p className="mt-0.5 truncate text-xs text-zinc-400">{subtitle}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close info modal"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-zinc-800 bg-zinc-900 font-mono text-sm text-slate-300 hover:border-zinc-600 hover:text-white"
          >
            ✕
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto bg-[#0b1017] p-4">
          <table className="w-full border-collapse text-left text-xs">
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.label}
                  className="border-b border-zinc-800/80 last:border-b-0"
                >
                  <th className="w-36 whitespace-nowrap py-2.5 pr-4 align-top font-medium text-zinc-400">
                    {row.label}
                  </th>
                  <td
                    className={`break-all py-2.5 text-zinc-100 ${
                      row.mono ? "font-mono text-[11px]" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span>{row.value}</span>
                      {row.copyable && (
                        <button
                          type="button"
                          onClick={() => handleCopy(row.label, row.value)}
                          className="shrink-0 rounded border border-zinc-700 bg-zinc-900 px-2 py-0.5 font-sans text-[10px] text-slate-300 hover:border-zinc-500 hover:text-white"
                        >
                          {copiedKey === row.label ? "Copied" : "Copy"}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
