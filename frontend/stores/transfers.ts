import { create } from "zustand";

export type TransferType = "upload" | "download" | "lan-upload" | "lan-download";
export type TransferStatus = "pending" | "transferring" | "paused" | "completed" | "error" | "canceled";

export interface TransferTask {
  id: string;
  filename: string;
  type: TransferType;
  status: TransferStatus;
  progress: number;
  loaded: number;
  total: number;
  error?: string;
  createdAt: number;
  fileId?: string;
  isMultipart?: boolean;
}

export interface TransferRunnerContext {
  taskId: string;
  signal: AbortSignal;
  onProgress: (loaded: number, total: number) => void;
}

export type TransferRunner = (ctx: TransferRunnerContext) => Promise<void>;

interface NewTaskInput {
  filename: string;
  type: TransferType;
  total: number;
  fileId?: string;
  isMultipart?: boolean;
}

const abortControllers = new Map<string, AbortController>();
const runners = new Map<string, TransferRunner>();
const QUEUE_LIMITS: Partial<Record<TransferType, number>> = { upload: 3, download: 3 };

interface TransferState {
  tasks: TransferTask[];
  addTask: (task: NewTaskInput) => string;
  enqueue: (task: NewTaskInput, runner: TransferRunner) => string;
  updateTask: (id: string, updates: Partial<TransferTask>) => void;
  removeTask: (id: string) => void;
  clearCompleted: () => void;
  hasActive: () => boolean;
  pauseTask: (id: string) => void;
  resumeTask: (id: string) => void;
  cancelTask: (id: string) => void;
}

const MAX_COMPLETED_TASKS = 30;
let counter = 0;
function genId() {
  counter += 1;
  return `transfer-${Date.now()}-${counter}`;
}

function findTask(id: string): TransferTask | undefined {
  return useTransferStore.getState().tasks.find((t) => t.id === id);
}

function pumpQueue(): void {
  const state = useTransferStore.getState();
  const running: Partial<Record<TransferType, number>> = {};
  for (const task of state.tasks) {
    if (task.status === "transferring") {
      running[task.type] = (running[task.type] ?? 0) + 1;
    }
  }
  const queued = state.tasks
    .filter((task) => task.status === "pending" && runners.has(task.id))
    .sort((a, b) => a.createdAt - b.createdAt);

  for (const task of queued) {
    const limit = QUEUE_LIMITS[task.type] ?? 1;
    const active = running[task.type] ?? 0;
    if (active >= limit) continue;
    running[task.type] = active + 1;
    void startTask(task.id);
  }
}

async function startTask(taskId: string): Promise<void> {
  const runner = runners.get(taskId);
  if (!runner) return;
  const controller = new AbortController();
  abortControllers.set(taskId, controller);
  useTransferStore.getState().updateTask(taskId, {
    status: "transferring",
    loaded: 0,
    progress: 0,
    error: undefined,
  });

  try {
    await runner({
      taskId,
      signal: controller.signal,
      onProgress: (loaded, total) =>
        useTransferStore.getState().updateTask(taskId, { loaded, total }),
    });
    const task = findTask(taskId);
    if (task && task.status === "transferring") {
      useTransferStore.getState().updateTask(
        taskId,
        task.total > 0
          ? { status: "completed", loaded: task.total, progress: 100 }
          : { status: "completed", progress: 100 }
      );
    }
  } catch (err) {
    const task = findTask(taskId);
    const interrupted = task?.status === "paused" || task?.status === "canceled";
    if (!interrupted) {
      useTransferStore.getState().updateTask(taskId, {
        status: "error",
        error: err instanceof Error ? err.message : "传输失败",
      });
    }
  } finally {
    abortControllers.delete(taskId);
    pumpQueue();
  }
}

export const useTransferStore = create<TransferState>((set, get) => ({
  tasks: [],

  addTask({ filename, type, total, fileId, isMultipart }) {
    const id = genId();
    const task: TransferTask = {
      id,
      filename,
      type,
      status: "pending",
      progress: 0,
      loaded: 0,
      total,
      createdAt: Date.now(),
      fileId,
      isMultipart,
    };
    set((state) => ({ tasks: [task, ...state.tasks] }));
    return id;
  },

  enqueue(task, runner) {
    const id = get().addTask(task);
    runners.set(id, runner);
    pumpQueue();
    return id;
  },

  updateTask(id, updates) {
    set((state) => {
      const updated = state.tasks.map((t) =>
        t.id === id
          ? {
              ...t,
              ...updates,
              progress:
                updates.total !== undefined || updates.loaded !== undefined
                  ? Math.min(
                      100,
                      Math.round(
                        ((updates.loaded ?? t.loaded) /
                          (updates.total ?? (t.total || 1))) *
                          100
                      )
                    )
                  : t.progress,
            }
          : t
      );
      const isTerminal = updates.status === "completed" || updates.status === "error" || updates.status === "canceled";
      if (isTerminal) {
        abortControllers.delete(id);
        const active = updated.filter(
          (t) => t.status !== "completed" && t.status !== "error" && t.status !== "canceled"
        );
        const completed = updated.filter(
          (t) => t.status === "completed" || t.status === "error" || t.status === "canceled"
        );
        return { tasks: [...active, ...completed.slice(0, MAX_COMPLETED_TASKS)] };
      }
      return { tasks: updated };
    });
  },

  removeTask(id) {
    abortControllers.delete(id);
    runners.delete(id);
    set((state) => ({ tasks: state.tasks.filter((t) => t.id !== id) }));
  },

  clearCompleted() {
    set((state) => {
      const keep = state.tasks.filter(
        (t) => t.status !== "completed" && t.status !== "error" && t.status !== "canceled"
      );
      const remove = state.tasks.filter(
        (t) => t.status === "completed" || t.status === "error" || t.status === "canceled"
      );
      for (const t of remove) {
        abortControllers.delete(t.id);
        runners.delete(t.id);
      }
      return { tasks: keep };
    });
  },

  hasActive() {
    return get().tasks.some(
      (t) => t.status === "pending" || t.status === "transferring"
    );
  },

  pauseTask(id) {
    const controller = abortControllers.get(id);
    if (controller) {
      controller.abort();
      abortControllers.delete(id);
    }
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === id && t.status === "transferring" ? { ...t, status: "paused" } : t
      ),
    }));
    pumpQueue();
  },

  resumeTask(id) {
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === id && t.status === "paused" ? { ...t, status: "pending" } : t
      ),
    }));
    pumpQueue();
  },

  cancelTask(id) {
    const controller = abortControllers.get(id);
    if (controller) {
      controller.abort();
      abortControllers.delete(id);
    }
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === id && (t.status === "transferring" || t.status === "paused" || t.status === "pending")
          ? { ...t, status: "canceled" }
          : t
      ),
    }));
    pumpQueue();
  },
}));