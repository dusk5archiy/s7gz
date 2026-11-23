"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

export interface FuelTaskState<T = unknown> {
  task_id: string;
  label: string;
  status: "running" | "done" | "error";
  logs: string[];
  done: number | null;
  total: number | null;
  result: T | null;
  error: string | null;
}

interface FuelTerminalSnapshot {
  busy: boolean;
  active_label: string | null;
  active_task: FuelTaskState | null;
  logs: string[];
}

interface FuelTerminalContextValue {
  busy: boolean;
  activeLabel: string | null;
  task: FuelTaskState | null;
  logs: string[];
  terminalOpen: boolean;
  setTerminalOpen: (open: boolean) => void;
  runTask: <T = unknown>(
    payload: Record<string, unknown>,
    options?: { openTerminal?: boolean },
  ) => Promise<T>;
}

const FuelTerminalContext = createContext<FuelTerminalContextValue | null>(null);

export const DISABLED_BUSY_BTN_CLASS =
  "cursor-not-allowed border-zinc-600 bg-zinc-600 text-white opacity-75 hover:bg-zinc-600";

export function useFuelTerminal(): FuelTerminalContextValue {
  const ctx = useContext(FuelTerminalContext);
  if (!ctx) {
    throw new Error("useFuelTerminal must be used inside FuelTerminalProvider");
  }
  return ctx;
}

export function FuelTerminalProvider({ children }: { children: ReactNode }) {
  const [busy, setBusy] = useState(false);
  const [activeLabel, setActiveLabel] = useState<string | null>(null);
  const [task, setTask] = useState<FuelTaskState | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const mountedRef = useRef(true);

  const syncCurrentState = useCallback(async () => {
    try {
      const res = await fetch("/api/fuel-tasks/current");
      if (!res.ok || !mountedRef.current) return;
      const snap = (await res.json()) as FuelTerminalSnapshot;
      setBusy(snap.busy);
      setActiveLabel(snap.active_label);
      if (snap.active_task) setTask(snap.active_task);
      setLogs(snap.logs ?? []);
    } catch {
      // Ignore transient network errors during polling
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    const initId = window.setTimeout(() => {
      void syncCurrentState();
    }, 0);
    return () => {
      mountedRef.current = false;
      window.clearTimeout(initId);
    };
  }, [syncCurrentState]);

  useEffect(() => {
    if (!busy && !terminalOpen) return;
    const id = window.setInterval(() => {
      void syncCurrentState();
    }, 500);
    return () => window.clearInterval(id);
  }, [busy, terminalOpen, syncCurrentState]);

  const runTask = useCallback(
    async <T = unknown>(
      payload: Record<string, unknown>,
      options: { openTerminal?: boolean } = { openTerminal: true },
    ): Promise<T> => {
      if (options.openTerminal !== false) {
        setTerminalOpen(true);
      }
      setBusy(true);
      try {
        const startRes = await fetch("/api/fuel-tasks/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!startRes.ok) {
          const text = await startRes.text();
          let detail = text;
          try {
            const parsed = JSON.parse(text) as { detail?: string };
            if (parsed.detail) detail = parsed.detail;
          } catch {
            // Keep raw text
          }
          const msg = detail || `HTTP ${startRes.status}`;
          setLogs((prev) => [...prev, `Error: ${msg}`]);
          setTerminalOpen(true);
          throw new Error(msg);
        }
        const { task_id } = (await startRes.json()) as { task_id: string };

        while (mountedRef.current) {
          const pollRes = await fetch(`/api/fuel-tasks/${encodeURIComponent(task_id)}`);
          if (!pollRes.ok) {
            throw new Error(`HTTP ${pollRes.status}: ${await pollRes.text()}`);
          }
          const next = (await pollRes.json()) as FuelTaskState<T>;
          setTask(next);
          setActiveLabel(next.status === "running" ? next.label : null);
          setLogs(next.logs);
          if (next.status === "done") {
            return next.result as T;
          }
          if (next.status === "error") {
            setTerminalOpen(true);
            throw new Error(next.error ?? "Fuel task failed");
          }
          await new Promise((r) => setTimeout(r, 350));
        }
        throw new Error("Task interrupted");
      } finally {
        await syncCurrentState();
      }
    },
    [syncCurrentState],
  );

  return (
    <FuelTerminalContext.Provider
      value={{
        busy,
        activeLabel,
        task,
        logs,
        terminalOpen,
        setTerminalOpen,
        runTask,
      }}
    >
      {children}
      <FuelTerminalModal
        open={terminalOpen}
        busy={busy}
        activeLabel={activeLabel}
        task={task}
        logs={logs}
        onClose={() => setTerminalOpen(false)}
      />
    </FuelTerminalContext.Provider>
  );
}

function FuelTerminalModal({
  open,
  busy,
  activeLabel,
  task,
  logs,
  onClose,
}: {
  open: boolean;
  busy: boolean;
  activeLabel: string | null;
  task: FuelTaskState | null;
  logs: string[];
  onClose: () => void;
}) {
  const logEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (open) {
      logEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [logs.length, open]);

  if (!open) return null;

  const hasRatio =
    task !== null &&
    typeof task.done === "number" &&
    typeof task.total === "number" &&
    task.total > 0;
  const pct = hasRatio
    ? Math.min(100, Math.round((task!.done! / task!.total!) * 100))
    : task?.status === "done" && !busy
      ? 100
      : 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        className="flex h-[72vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl border border-zinc-800 bg-[#070a0f] text-zinc-100 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950 px-4 py-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <span
              className={`h-2.5 w-2.5 shrink-0 rounded-full ${
                busy
                  ? "animate-pulse bg-sky-400"
                  : task?.status === "error"
                    ? "bg-rose-400"
                    : "bg-emerald-400"
              }`}
            />
            <span className="truncate font-mono text-sm font-semibold">
              {activeLabel ?? task?.label ?? "Fuel Terminal"}
            </span>
            {hasRatio && (
              <span className="shrink-0 rounded bg-sky-500/15 px-2 py-0.5 font-mono text-[11px] text-sky-300">
                {task!.done}/{task!.total} ({pct}%)
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close terminal modal"
            className="flex h-8 w-8 items-center justify-center rounded-md border border-zinc-800 bg-zinc-900 font-mono text-sm text-slate-300 hover:border-zinc-600 hover:text-white"
          >
            ✕
          </button>
        </div>

        <div className="h-1.5 w-full bg-zinc-900">
          {busy && !hasRatio ? (
            <div className="h-full w-1/3 animate-pulse bg-sky-500" />
          ) : (
            <div
              className={`h-full transition-all duration-200 ${
                task?.status === "error"
                  ? "bg-rose-500"
                  : busy
                    ? "bg-sky-500"
                    : "bg-emerald-500"
              }`}
              style={{ width: `${pct}%` }}
            />
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto bg-[#0b1017] p-4 font-mono text-xs leading-relaxed text-zinc-300">
          {logs.length === 0 ? (
            <div className="text-zinc-500">No Fuel operations logged yet.</div>
          ) : (
            logs.map((line, idx) => (
              <div
                key={idx}
                className={`whitespace-pre-wrap break-all ${
                  line.startsWith("Error:")
                    ? "text-rose-400"
                    : line.startsWith("Completed:")
                      ? "text-emerald-400"
                      : line.startsWith("Started:")
                        ? "text-sky-300"
                        : ""
                }`}
              >
                {line}
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}
