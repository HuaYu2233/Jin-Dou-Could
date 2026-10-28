import { describe, it, expect } from "vitest";
import { formatSize, formatDate } from "@/lib/utils/format";

describe("formatSize", () => {
  it("formats bytes as KB", () => {
    expect(formatSize(512)).toBe("1 KB");
    expect(formatSize(1024)).toBe("1 KB");
  });

  it("formats MB", () => {
    expect(formatSize(1024 * 1024)).toBe("1.0 MB");
    expect(formatSize(5 * 1024 * 1024)).toBe("5.0 MB");
  });

  it("formats GB", () => {
    expect(formatSize(1024 * 1024 * 1024)).toBe("1.00 GB");
    expect(formatSize(2.5 * 1024 * 1024 * 1024)).toBe("2.50 GB");
  });

  it("formats zero", () => {
    expect(formatSize(0)).toBe("0 KB");
  });

  it("boundary between KB and MB", () => {
    const justUnder1MB = 1024 * 1024 - 1;
    expect(formatSize(justUnder1MB)).toMatch(/KB$/);
  });

  it("boundary between MB and GB", () => {
    const justUnder1GB = 1024 * 1024 * 1024 - 1;
    expect(formatSize(justUnder1GB)).toMatch(/MB$/);
  });
});

describe("formatDate", () => {
  it("formats ISO string", () => {
    const result = formatDate("2025-01-15T10:30:00Z");
    expect(result).toBeTruthy();
    expect(typeof result).toBe("string");
  });

  it("handles different dates", () => {
    const r1 = formatDate("2025-01-01T00:00:00Z");
    const r2 = formatDate("2025-12-31T23:59:59Z");
    expect(r1).not.toBe(r2);
  });
});