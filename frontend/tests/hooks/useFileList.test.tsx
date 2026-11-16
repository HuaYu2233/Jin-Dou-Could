import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/lib/api/files", () => ({
  listFiles: vi.fn(),
  listTrashFiles: vi.fn(),
  listTrashFolders: vi.fn(),
  searchFiles: vi.fn(),
  listFolderContents: vi.fn(),
}));

import { useFileList } from "@/app/dashboard/hooks/useFileList";
import type { CategoryId } from "@/app/dashboard/types";

type HookResult = ReturnType<typeof useFileList>;

async function mountFileList(category: CategoryId) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const container = document.createElement("div");
  const root: Root = createRoot(container);
  const holder: { current: HookResult | null } = { current: null };

  function Probe() {
    holder.current = useFileList(category);
    return null;
  }

  await act(async () => {
    root.render(
      <QueryClientProvider client={client}>
        <Probe />
      </QueryClientProvider>
    );
  });

  return {
    holder,
    async run(action: (result: HookResult) => void) {
      await act(async () => {
        action(holder.current!);
      });
    },
    async unmount() {
      await act(async () => {
        root.unmount();
      });
    },
  };
}

describe("useFileList 手动错误与总数覆盖", () => {
  beforeEach(() => {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("分享分类查询被禁用时，setTotal 覆盖分页总数", async () => {
    const view = await mountFileList("shares");

    expect(view.holder.current!.total).toBe(0);
    await view.run((result) => result.setTotal(42));
    expect(view.holder.current!.total).toBe(42);

    await view.unmount();
  });

  it("setError 把操作错误暴露到 error 字段", async () => {
    const view = await mountFileList("shares");

    expect(view.holder.current!.error).toBe("");
    await view.run((result) => result.setError("删除失败"));
    expect(view.holder.current!.error).toBe("删除失败");
    await view.run((result) => result.setError(""));
    expect(view.holder.current!.error).toBe("");

    await view.unmount();
  });

  it("翻页后旧的操作错误不再显示，但总数保持", async () => {
    const view = await mountFileList("shares");

    await view.run((result) => result.setError("删除失败"));
    await view.run((result) => result.setTotal(42));
    expect(view.holder.current!.error).toBe("删除失败");
    expect(view.holder.current!.total).toBe(42);

    await view.run((result) => result.setPage(2));
    expect(view.holder.current!.error).toBe("");
    expect(view.holder.current!.total).toBe(42);

    await view.unmount();
  });
});