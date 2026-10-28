import { describe, it, expect, beforeEach } from "vitest";
import { useTransferStore } from "@/stores/transfers";

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