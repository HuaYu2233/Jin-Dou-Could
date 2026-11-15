import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  LAN_CHUNK_THRESHOLD,
  LAN_PART_SIZE,
  sendDriveFilesToRoom,
  uploadLanFileChunked,
} from "@/lib/api/lanTransfer";

function jsonResponse(data: unknown): Response {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("lanTransfer chunked upload", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("uses 16MB parts and a 32MB chunk threshold", () => {
    expect(LAN_PART_SIZE).toBe(16 * 1024 * 1024);
    expect(LAN_CHUNK_THRESHOLD).toBe(32 * 1024 * 1024);
    expect(LAN_CHUNK_THRESHOLD).toBeGreaterThanOrEqual(LAN_PART_SIZE);
  });

  it("splits the file into the expected parts and completes the upload", async () => {
    const calls: string[] = [];
    const partSizes: number[] = [];

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push(url);
      if (url.includes("/multipart/init")) {
        return jsonResponse({
          upload_id: "upload-1",
          storage_key: "lan-transfer/room/upload-1",
          part_size: LAN_PART_SIZE,
          total_parts: 2,
        });
      }
      if (url.includes("/multipart/part")) {
        const body = init?.body as Blob;
        partSizes.push(body.size);
        const params = new URL(url, "http://localhost").searchParams;
        const partNumber = Number(params.get("part_number"));
        return jsonResponse({ etag: `etag-${partNumber}`, part_number: partNumber });
      }
      if (url.includes("/multipart/complete")) {
        const body = JSON.parse(String(init?.body)) as { parts: { PartNumber: number; ETag: string }[] };
        return jsonResponse({
          id: "file-1",
          filename: "big.bin",
          size: LAN_PART_SIZE + 1024,
          mime_type: "application/octet-stream",
          file_type: "other",
          uploader: "匿名",
          created_at: "2026-01-01T00:00:00Z",
          parts: body.parts.length,
        });
      }
      throw new Error(`unexpected request: ${url}`);
    }) as unknown as typeof fetch;

    const size = LAN_PART_SIZE + 1024;
    const file = new File([new Uint8Array(size)], "big.bin", { type: "application/octet-stream" });
    const progress: number[] = [];

    const result = await uploadLanFileChunked("room-1", "token-1", file, (loaded) => progress.push(loaded));

    expect(calls.filter((u) => u.includes("/multipart/part"))).toHaveLength(2);
    expect(partSizes).toEqual([LAN_PART_SIZE, 1024]);
    expect(progress.at(-1)).toBe(size);
    expect(result.filename).toBe("big.bin");
  });

  it("aborts the multipart upload when a part fails", async () => {
    const calls: string[] = [];
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      calls.push(url);
      if (url.includes("/multipart/init")) {
        return jsonResponse({
          upload_id: "upload-2",
          storage_key: "lan-transfer/room/upload-2",
          part_size: LAN_PART_SIZE,
          total_parts: 1,
        });
      }
      if (url.includes("/multipart/part")) {
        return new Response(JSON.stringify({ detail: "分片上传失败" }), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/multipart/abort")) {
        return jsonResponse({ message: "上传已取消" });
      }
      throw new Error(`unexpected request: ${url}`);
    }) as unknown as typeof fetch;

    const file = new File([new Uint8Array(LAN_PART_SIZE)], "fail.bin");
    await expect(uploadLanFileChunked("room-1", "token-1", file, () => {})).rejects.toThrow(
      "分片上传失败"
    );
    expect(calls.some((u) => u.includes("/multipart/abort"))).toBe(true);
  });
});

describe("sendDriveFilesToRoom", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("posts the selected drive file ids to the room", async () => {
    const calls: { url: string; body: unknown }[] = [];
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), body: init?.body ? JSON.parse(String(init.body)) : null });
      return jsonResponse({ items: [], used_size: 0, file_count: 0 });
    }) as unknown as typeof fetch;

    const result = await sendDriveFilesToRoom("room-1", ["file-1", "file-2"]);

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toContain("/api/v1/lan-transfer/rooms/room-1/send-from-files");
    expect(calls[0].body).toEqual({ file_ids: ["file-1", "file-2"] });
    expect(result.file_count).toBe(0);
  });
});