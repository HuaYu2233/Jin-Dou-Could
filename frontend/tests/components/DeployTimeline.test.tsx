import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import DeployTimeline from "@/app/admin/components/DeployTimeline";

const STEPS = [
  { key: "preflight", label: "生产编排校验" },
  { key: "build", label: "镜像构建" },
  { key: "health", label: "健康检查" },
];

describe("DeployTimeline 步骤与进度渲染", () => {
  let root: Root;
  let container: HTMLElement;

  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>';
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    container = document.getElementById("root")!;
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    vi.unstubAllGlobals();
  });

  async function render(props: Partial<Parameters<typeof DeployTimeline>[0]> = {}) {
    await act(async () => {
      root.render(
        <DeployTimeline
          steps={STEPS}
          currentStep="build"
          stepIndex={1}
          pct={40}
          status="running"
          {...props}
        />
      );
    });
  }

  it("渲染全部步骤文案与百分比", async () => {
    await render();
    for (const step of STEPS) {
      expect(container.textContent).toContain(step.label);
    }
    expect(container.textContent).toContain("40%");
  });

  it("进度条宽度按 pct 设置", async () => {
    await render({ pct: 40 });
    const fill = container.querySelector('[class*="fill"]') as HTMLElement;
    expect(fill.style.width).toBe("40%");
  });

  it("pct 越界时钳制到 0-100", async () => {
    await render({ pct: 150 });
    const fill = container.querySelector('[class*="fill"]') as HTMLElement;
    expect(fill.style.width).toBe("100%");

    await render({ pct: -20 });
    const clamped = container.querySelector('[class*="fill"]') as HTMLElement;
    expect(clamped.style.width).toBe("0%");
  });

  it("已完成步骤标记 done，当前步骤标记 active", async () => {
    await render({ currentStep: "build", stepIndex: 1, status: "running" });
    const items = container.querySelectorAll("li");
    expect(items[0].className).toContain("done");
    expect(items[1].className).toContain("active");
    expect(items[2].className).toContain("pending");
  });

  it("失败时当前步骤标记 failed", async () => {
    await render({ currentStep: "build", stepIndex: 1, status: "failed" });
    const items = container.querySelectorAll("li");
    expect(items[1].className).toContain("failed");
  });

  it("成功后当前步骤标记 done", async () => {
    await render({ currentStep: "health", stepIndex: 2, status: "success" });
    const items = container.querySelectorAll("li");
    expect(items[2].className).toContain("done");
  });

  it("没有步骤时不渲染", async () => {
    await render({ steps: [] });
    expect(container.innerHTML).toBe("");
  });
});