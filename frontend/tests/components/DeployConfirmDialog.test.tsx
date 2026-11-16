import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import DeployConfirmDialog from "@/app/admin/components/DeployConfirmDialog";

function typeInto(node: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(node, value);
  node.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("DeployConfirmDialog 危险动作二次确认", () => {
  let root: Root;
  let container: HTMLElement;
  const onConfirm = vi.fn();
  const onClose = vi.fn();

  beforeEach(() => {
    onConfirm.mockClear();
    onClose.mockClear();
    document.body.innerHTML = '<div id="root"></div>';
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    container = document.getElementById("root")!;
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    vi.unstubAllGlobals();
  });

  async function render(action: string | null) {
    await act(async () => {
      root.render(
        <DeployConfirmDialog
          action={action}
          saving={false}
          onConfirm={onConfirm}
          onClose={onClose}
        />
      );
    });
  }

  function confirmButton(): HTMLButtonElement {
    const buttons = container.querySelectorAll("button");
    return buttons[buttons.length - 1] as HTMLButtonElement;
  }

  it("action 为空时不渲染弹窗", async () => {
    await render(null);
    expect(container.innerHTML).toBe("");
  });

  it("输入与动作名不匹配时确认不生效", async () => {
    await render("deploy");
    const input = container.querySelector("input") as HTMLInputElement;
    await act(async () => {
      typeInto(input, "deploy-x");
    });
    await act(async () => {
      confirmButton().click();
    });
    expect(onConfirm).not.toHaveBeenCalled();
    expect(container.textContent).toContain("输入不匹配");
  });

  it("输入与动作名一致时确认生效", async () => {
    await render("deploy");
    const input = container.querySelector("input") as HTMLInputElement;
    await act(async () => {
      typeInto(input, "deploy");
    });
    await act(async () => {
      confirmButton().click();
    });
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("切换动作后输入被清空", async () => {
    await render("deploy");
    const input = container.querySelector("input") as HTMLInputElement;
    await act(async () => {
      typeInto(input, "deploy");
    });
    await render("rollback");
    const next = container.querySelector("input") as HTMLInputElement;
    expect(next.value).toBe("");
    expect(container.textContent).toContain("rollback");
  });

  it("点击取消触发关闭", async () => {
    await render("rollback");
    const cancel = container.querySelectorAll("button")[0] as HTMLButtonElement;
    await act(async () => {
      cancel.click();
    });
    expect(onClose).toHaveBeenCalled();
  });
});