import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api/deploy", () => ({
  getDeployStatus: vi.fn(),
  getDeployContainers: vi.fn(),
  getDeployVersions: vi.fn(),
  getDeployTask: vi.fn(),
  listDeployHistory: vi.fn(),
  submitDeployAction: vi.fn(),
  confirmDeployAction: vi.fn(),
}));

import { useAdminDeploy } from "@/app/admin/hooks/useAdminDeploy";
import {
  getDeployContainers,
  getDeployStatus,
  getDeployTask,
  getDeployVersions,
  listDeployHistory,
} from "@/lib/api/deploy";

type HookResult = ReturnType<typeof useAdminDeploy>;

const TASK = {
  task_id: "task-1",
  action: "check",
  target: null,
  status: "running",
  step: "preflight",
  step_index: 1,
  total_steps: 2,
  pct: 10,
  started_at: "2026-11-16T00:00:00Z",
  updated_at: "2026-11-16T00:00:10Z",
  finished_at: null,
  logs: [],
  error: null,
  stalled: false,
};

const STATUS = {
  enabled: true,
  runner_online: true,
  running_task_id: "task-1",
  allowed_actions: ["check", "deploy", "restart"],
  last_result: null,
};

const CONTAINERS = {
  available: true,
  collected_at: "2026-11-16T00:00:00Z",
  compose_project: "jindou",
  heartbeat_age_seconds: 3,
  runner_online: true,
  services: [],
};

const VERSIONS = {
  app_version: "1.0.0",
  image_tags: {},
  compose_hash: null,
  git_commit: null,
  collected_at: null,
};

async function mountDeploy() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const container = document.createElement("div");
  const root: Root = createRoot(container);
  const holder: { current: HookResult | null } = { current: null };

  function Probe() {
    holder.current = useAdminDeploy();
    return null;
  }

  await act(async () => {
    root.render(
      <QueryClientProvider client={client}>
        <Probe />
      </QueryClientProvider>
    );
  });

  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });

  return {
    holder,
    client,
    async unmount() {
      await act(async () => {
        root.unmount();
      });
    },
  };
}

function intervalOf(client: QueryClient, keyPart: string) {
  const query = client
    .getQueryCache()
    .findAll()
    .find((q) => JSON.stringify(q.queryKey).includes(keyPart));
  expect(query).toBeDefined();
  return (query!.options as { refetchInterval?: unknown }).refetchInterval;
}

describe("useAdminDeploy 轮询策略", () => {
  beforeEach(() => {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    vi.mocked(getDeployStatus).mockResolvedValue(STATUS);
    vi.mocked(getDeployContainers).mockResolvedValue(CONTAINERS);
    vi.mocked(getDeployVersions).mockResolvedValue(VERSIONS);
    vi.mocked(getDeployTask).mockResolvedValue(TASK);
    vi.mocked(listDeployHistory).mockResolvedValue([]);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("status 每 5s、containers 每 15s 轮询", async () => {
    const mounted = await mountDeploy();
    expect(intervalOf(mounted.client, "status")).toBe(5000);
    expect(intervalOf(mounted.client, "containers")).toBe(15000);
    await mounted.unmount();
  });

  it("任务运行中按 2s 轮询，终态停止", async () => {
    const mounted = await mountDeploy();
    const refetch = intervalOf(mounted.client, "task");
    expect(typeof refetch).toBe("function");
    const fn = refetch as (q: { state: { data?: { status?: string } } }) => unknown;
    expect(fn({ state: { data: { status: "running" } } })).toBe(2000);
    expect(fn({ state: { data: { status: "queued" } } })).toBe(2000);
    expect(fn({ state: { data: { status: "success" } } })).toBe(false);
    expect(fn({ state: { data: { status: "failed" } } })).toBe(false);
    expect(fn({ state: { data: { status: "rolled_back" } } })).toBe(false);
    await mounted.unmount();
  });

  it("运行中的任务来自 status，无需手动指定", async () => {
    const mounted = await mountDeploy();
    expect(mounted.holder.current?.taskId).toBe("task-1");
    await mounted.unmount();
  });

  it("三路轮询合计每分钟不超过 60 次限流阈值", async () => {
    const mounted = await mountDeploy();
    const statusMs = intervalOf(mounted.client, "status") as number;
    const containersMs = intervalOf(mounted.client, "containers") as number;
    const taskMs = 2000;
    const perMinute = 60 / (statusMs / 1000) + 60 / (containersMs / 1000) + 60 / (taskMs / 1000);
    expect(perMinute).toBe(46);
    expect(perMinute).toBeLessThan(60);
    await mounted.unmount();
  });

  it("控制台未启用时标记 disabled", async () => {
    vi.mocked(getDeployStatus).mockRejectedValue(new Error("部署控制台未启用"));
    const mounted = await mountDeploy();
    expect(mounted.holder.current?.disabled).toBe(true);
    await mounted.unmount();
  });
});