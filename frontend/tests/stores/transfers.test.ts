import { describe, it, expect, beforeEach, vi } from "vitest";
import { useTransferStore, type TransferStatus, type TransferType } from "@/stores/transfers";

function taskStatus(id: string): TransferStatus | undefined {
  return useTransferStore.getState().tasks.find((t) => t.id === id)?.status;
}

function countByStatus(status: TransferStatus, type: TransferType = "upload"): number {
  return useTransferStore.getState().tasks.filter((t) => t.status === status && t.type === type).length;
}

function gate() {
  let resolve!: () => void;
  const promise = new Promise<void>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

describe("useTransferStore", () => {
  beforeEach(() => {
    useTransferStore.setState({ tasks: [] });
  });

  it("starts with empty tasks", () => {
    expect(useTransferStore.getState().tasks).toHaveLength(0);
  });

  it("addTask creates a pending task", () => {
    const id = useTransferStore.getState().addTask({
      filename: "test.pdf",
      type: "upload",
      total: 1024,
    });
    expect(id).toBeTruthy();
    const task = useTransferStore.getState().tasks.find((t) => t.id === id);
    expect(task).toBeDefined();
    expect(task!.filename).toBe("test.pdf");
    expect(task!.status).toBe("pending");
    expect(task!.progress).toBe(0);
  });

  it("updateTask modifies a task", () => {
    const id = useTransferStore.getState().addTask({
      filename: "test.pdf",
      type: "upload",
      total: 1024,
    });
    useTransferStore.getState().updateTask(id, { loaded: 512, status: "transferring" });
    const task = useTransferStore.getState().tasks.find((t) => t.id === id);
    expect(task!.progress).toBe(50);
    expect(task!.status).toBe("transferring");
  });

  it("updateTask clamps progress at 100", () => {
    const id = useTransferStore.getState().addTask({
      filename: "test.pdf",
      type: "upload",
      total: 100,
    });
    useTransferStore.getState().updateTask(id, { loaded: 250 });
    expect(useTransferStore.getState().tasks.find((t) => t.id === id)!.progress).toBe(100);
  });

  it("removeTask deletes a task", () => {
    const id = useTransferStore.getState().addTask({
      filename: "test.pdf",
      type: "upload",
      total: 1024,
    });
    useTransferStore.getState().removeTask(id);
    expect(useTransferStore.getState().tasks.find((t) => t.id === id)).toBeUndefined();
  });

  it("clearCompleted removes completed tasks", () => {
    const id1 = useTransferStore.getState().addTask({ filename: "a.txt", type: "upload", total: 100 });
    const id2 = useTransferStore.getState().addTask({ filename: "b.txt", type: "upload", total: 100 });
    useTransferStore.getState().updateTask(id1, { status: "completed" });
    useTransferStore.getState().clearCompleted();
    const tasks = useTransferStore.getState().tasks;
    expect(tasks.find((t) => t.id === id1)).toBeUndefined();
    expect(tasks.find((t) => t.id === id2)).toBeDefined();
  });

  it("hasActive returns true when transferring", () => {
    const id = useTransferStore.getState().addTask({ filename: "a.txt", type: "upload", total: 100 });
    expect(useTransferStore.getState().hasActive()).toBe(true);
    useTransferStore.getState().updateTask(id, { status: "completed" });
    expect(useTransferStore.getState().hasActive()).toBe(false);
  });
});

describe("useTransferStore queue", () => {
  beforeEach(() => {
    useTransferStore.setState({ tasks: [] });
  });

  it("starts an enqueued task immediately when a slot is free", async () => {
    const id = useTransferStore.getState().enqueue(
      { filename: "a.txt", type: "upload", total: 100 },
      async () => {}
    );

    expect(taskStatus(id)).toBe("transferring");

    await vi.waitFor(() => expect(taskStatus(id)).toBe("completed"));
    const task = useTransferStore.getState().tasks.find((t) => t.id === id)!;
    expect(task.loaded).toBe(100);
    expect(task.progress).toBe(100);
  });

  it("caps concurrent uploads and starts the next queued task", async () => {
    const gates = [gate(), gate(), gate(), gate()];
    const ids = gates.map((g, i) =>
      useTransferStore.getState().enqueue(
        { filename: `f${i}.txt`, type: "upload", total: 10 },
        () => g.promise
      )
    );

    expect(countByStatus("transferring")).toBe(3);
    expect(countByStatus("pending")).toBe(1);

    gates[0].resolve();
    await vi.waitFor(() => expect(taskStatus(ids[0])).toBe("completed"));

    expect(taskStatus(ids[3])).toBe("transferring");
    expect(countByStatus("transferring")).toBe(3);

    for (const g of gates.slice(1)) g.resolve();
    await vi.waitFor(() => expect(countByStatus("completed")).toBe(4));
  });

  it("frees a slot for the next queued task when a running task is canceled", () => {
    const gates = [gate(), gate(), gate(), gate()];
    const ids = gates.map((g, i) =>
      useTransferStore.getState().enqueue(
        { filename: `f${i}.txt`, type: "upload", total: 10 },
        () => g.promise
      )
    );

    useTransferStore.getState().cancelTask(ids[0]);

    expect(taskStatus(ids[0])).toBe("canceled");
    expect(taskStatus(ids[3])).toBe("transferring");
    expect(countByStatus("transferring")).toBe(3);
  });

  it("cancels a queued task without starting it", () => {
    const gates = [gate(), gate(), gate(), gate()];
    const ids = gates.map((g, i) =>
      useTransferStore.getState().enqueue(
        { filename: `f${i}.txt`, type: "upload", total: 10 },
        () => g.promise
      )
    );

    useTransferStore.getState().cancelTask(ids[3]);

    expect(taskStatus(ids[3])).toBe("canceled");
    expect(countByStatus("transferring")).toBe(3);
  });

  it("runs a paused task again after resume", async () => {
    let runs = 0;
    const id = useTransferStore.getState().enqueue(
      { filename: "a.txt", type: "upload", total: 100 },
      async () => {
        runs += 1;
      }
    );

    await vi.waitFor(() => expect(taskStatus(id)).toBe("completed"));

    useTransferStore.setState((state) => ({
      tasks: state.tasks.map((t) => (t.id === id ? { ...t, status: "paused" as const } : t)),
    }));
    useTransferStore.getState().resumeTask(id);

    expect(taskStatus(id)).toBe("transferring");
    await vi.waitFor(() => expect(runs).toBe(2));
  });

  it("records an error message when a runner rejects", async () => {
    const id = useTransferStore.getState().enqueue(
      { filename: "a.txt", type: "upload", total: 100 },
      async () => {
        throw new Error("网络异常");
      }
    );

    await vi.waitFor(() => expect(taskStatus(id)).toBe("error"));
    expect(useTransferStore.getState().tasks.find((t) => t.id === id)!.error).toBe("网络异常");
  });

  it("keeps a task paused instead of failed when the runner aborts on pause", async () => {
    const id = useTransferStore.getState().enqueue(
      { filename: "a.txt", type: "upload", total: 100 },
      ({ signal }) =>
        new Promise<void>((_resolve, reject) => {
          signal.addEventListener("abort", () => reject(new Error("已取消")));
        })
    );

    useTransferStore.getState().pauseTask(id);

    expect(taskStatus(id)).toBe("paused");
    await vi.waitFor(() => expect(taskStatus(id)).toBe("paused"));
    expect(useTransferStore.getState().tasks.find((t) => t.id === id)!.error).toBeUndefined();
  });

  it("does not start lan tasks that are not enqueued with a runner", () => {
    const id = useTransferStore.getState().addTask({
      filename: "lan.txt",
      type: "lan-upload",
      total: 10,
    });

    expect(taskStatus(id)).toBe("pending");
    expect(countByStatus("transferring", "lan-upload")).toBe(0);
  });
});