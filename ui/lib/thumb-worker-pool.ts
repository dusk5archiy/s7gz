import type { WorldSceneModel, WorldSceneVisual } from "@/lib/types";

type WorkerResult =
  | { id: number; blob: Blob }
  | { id: number; empty: true }
  | { id: number; error: string };

interface QueuedJob {
  id: number;
  affinityKey: string | null;
  payload: Record<string, unknown>;
  resolve: (url: string | null) => void;
  reject: (err: Error) => void;
}

interface WorkerSlot {
  index: number;
  worker: Worker;
  busy: boolean;
  current: QueuedJob | null;
}

let nextJobId = 1;
let poolDisabled = false;
const slots: WorkerSlot[] = [];
const jobQueue: QueuedJob[] = [];
// Maps a mesh asset_url -> preferred worker slot index so bursts sharing a heavy
// mesh (e.g. 11 x500 variants sharing NXP-HGD-CF.dae) reuse its parsed geometry.
const affinityToSlot = new Map<string, number>();

const POOL_IDLE_TERMINATE_MS = 8000;
let poolIdleTimer: ReturnType<typeof setTimeout> | null = null;

function cancelPoolIdleTerminate(): void {
  if (poolIdleTimer !== null) {
    clearTimeout(poolIdleTimer);
    poolIdleTimer = null;
  }
}

function schedulePoolIdleTerminate(): void {
  if (jobQueue.length > 0 || slots.some((s) => s.busy)) return;
  cancelPoolIdleTerminate();
  poolIdleTimer = setTimeout(() => {
    poolIdleTimer = null;
    if (jobQueue.length > 0 || slots.some((s) => s.busy)) return;
    for (const slot of slots) {
      slot.worker.terminate();
    }
    slots.length = 0;
    affinityToSlot.clear();
  }, POOL_IDLE_TERMINATE_MS);
}

export function withGeometryOnlyParam(assetUrl: string): string {
  const sep = assetUrl.includes("?") ? "&" : "?";
  return `${assetUrl}${sep}geometry_only=1`;
}

export function canUseThumbWorker(visuals: WorldSceneVisual[]): boolean {
  if (poolDisabled) return false;
  if (typeof window === "undefined") return false;
  if (typeof Worker === "undefined" || typeof OffscreenCanvas === "undefined") {
    return false;
  }
  return visuals.length > 0;
}

function getPoolSize(): number {
  const cores = typeof navigator !== "undefined" ? navigator.hardwareConcurrency || 4 : 2;
  return Math.min(3, Math.max(2, Math.floor(cores / 2)));
}

function primaryMeshKey(visuals: WorldSceneVisual[]): string | null {
  for (const v of visuals) {
    if (v.geometry.type === "mesh" && v.geometry.asset_url) {
      return v.geometry.asset_url;
    }
  }
  return null;
}

function pickJobForSlot(slotIdx: number): QueuedJob | undefined {
  if (jobQueue.length === 0) return undefined;

  // 1. Prefer a queued job whose primary mesh is already warm in this worker.
  const exactIdx = jobQueue.findIndex(
    (j) => j.affinityKey !== null && affinityToSlot.get(j.affinityKey) === slotIdx,
  );
  if (exactIdx !== -1) {
    return jobQueue.splice(exactIdx, 1)[0];
  }

  // 2. Otherwise pick a job whose primary mesh is NOT currently being handled by another worker.
  const uncontendedIdx = jobQueue.findIndex((j) => {
    if (!j.affinityKey) return true;
    const owner = affinityToSlot.get(j.affinityKey);
    if (owner === undefined) return true;
    const ownerSlot = slots[owner];
    return !ownerSlot || !ownerSlot.busy;
  });
  if (uncontendedIdx !== -1) {
    return jobQueue.splice(uncontendedIdx, 1)[0];
  }

  // 3. If all remaining jobs share an affinity with a busy worker, let that worker finish
  //    rather than duplicating the same heavy mesh download/parse across multiple workers.
  return undefined;
}

function dispatchNext(): void {
  if (jobQueue.length === 0) return;
  for (const slot of slots) {
    if (slot.busy) continue;
    const job = pickJobForSlot(slot.index);
    if (!job) continue;
    slot.busy = true;
    slot.current = job;
    if (job.affinityKey) {
      affinityToSlot.set(job.affinityKey, slot.index);
    }
    slot.worker.postMessage({ id: job.id, ...job.payload });
  }
}

function ensurePool(): boolean {
  if (poolDisabled) return false;
  if (slots.length > 0) return true;
  try {
    const size = getPoolSize();
    for (let i = 0; i < size; i++) {
      const worker = new Worker(new URL("./thumb.worker.ts", import.meta.url), {
        type: "module",
      });
      const slot: WorkerSlot = { index: i, worker, busy: false, current: null };
      worker.onmessage = (ev: MessageEvent<WorkerResult>) => {
        const res = ev.data;
        const job = slot.current;
        slot.busy = false;
        slot.current = null;
        if (job) {
          if ("blob" in res) {
            job.resolve(URL.createObjectURL(res.blob));
          } else if ("empty" in res) {
            job.resolve(null);
          } else {
            job.reject(new Error(res.error));
          }
        }
        dispatchNext();
        schedulePoolIdleTerminate();
      };
      worker.onerror = () => {
        const job = slot.current;
        slot.busy = false;
        slot.current = null;
        poolDisabled = true;
        if (job) {
          job.reject(new Error("Thumbnail worker failed"));
        }
        while (jobQueue.length > 0) {
          jobQueue.shift()?.reject(new Error("Thumbnail worker disabled"));
        }
      };
      slots.push(slot);
    }
    return true;
  } catch {
    poolDisabled = true;
    return false;
  }
}

function enqueue(
  payload: Record<string, unknown>,
  affinityKey: string | null,
): Promise<string | null> {
  cancelPoolIdleTerminate();
  if (!ensurePool()) {
    return Promise.reject(new Error("Thumbnail worker unavailable"));
  }
  return new Promise<string | null>((resolve, reject) => {
    const id = nextJobId++;
    jobQueue.push({ id, affinityKey, payload, resolve, reject });
    dispatchNext();
  });
}

export function renderModelThumbInWorker(
  visuals: WorldSceneVisual[],
  width = 240,
  height = 150,
): Promise<string | null> {
  return enqueue(
    {
      kind: "model",
      origin: window.location.origin,
      width,
      height,
      visuals,
    },
    primaryMeshKey(visuals),
  );
}

export function renderWorldThumbInWorker(
  models: WorldSceneModel[],
  width = 240,
  height = 150,
): Promise<string | null> {
  const firstVis = models.find((m) => m.visuals.length > 0)?.visuals ?? [];
  return enqueue(
    {
      kind: "world",
      origin: window.location.origin,
      width,
      height,
      models,
    },
    primaryMeshKey(firstVis),
  );
}
