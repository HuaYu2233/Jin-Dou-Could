import { create } from "zustand";

export type TransferType = "upload" | "download";
export type TransferStatus = "pending" | "transferring" | "completed" | "error" | "canceled";

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
}

interface TransferState {
  tasks: TransferTask[];
  addTask: (task: {
    filename: string;
    type: TransferType;
    total: number;
    fileId?: string;
  }) => string;
  updateTask: (id: string, updates: Partial<TransferTask>) => void;
  removeTask: (id: string) => void;
  clearCompleted: () => void;
  hasActive: () => boolean;
}

let counter = 0;
function genId() {
  counter += 1;
  return `transfer-${Date.now()}-${counter}`;
}

export const useTransferStore = create<TransferState>((set, get) => ({
  tasks: [],

  addTask({ filename, type, total, fileId }) {
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
    };
    set((state) => ({ tasks: [task, ...state.tasks] }));
    return id;
  },

  updateTask(id, updates) {
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === id
          ? {
              ...t,
              ...updates,
              progress:
                updates.total !== undefined || updates.loaded !== undefined
                  ? Math.round(
                      ((updates.loaded ?? t.loaded) /
                        (updates.total ?? (t.total || 1))) *
                        100
                    )
                  : t.progress,
            }
          : t
      ),
    }));
  },

  removeTask(id) {
    set((state) => ({ tasks: state.tasks.filter((t) => t.id !== id) }));
  },

  clearCompleted() {
    set((state) => ({
      tasks: state.tasks.filter(
        (t) => t.status !== "completed" && t.status !== "error" && t.status !== "canceled"
      ),
    }));
  },

  hasActive() {
    return get().tasks.some(
      (t) => t.status === "pending" || t.status === "transferring"
    );
  },
}));