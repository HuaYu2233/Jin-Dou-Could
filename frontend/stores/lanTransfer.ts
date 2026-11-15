import { create } from "zustand";
import type { LanFileItem, LanRoom } from "@/lib/api/lanTransfer";

interface LanTransferState {
  room: LanRoom | null;
  roomToken: string | null;
  files: LanFileItem[];
  usedSize: number;
  maxTotalSize: number;
  fileCount: number;
  available: boolean | null;
  setRoom: (room: LanRoom | null) => void;
  setRoomToken: (token: string | null) => void;
  setFiles: (payload: { items: LanFileItem[]; used_size: number; max_total_size: number; file_count: number }) => void;
  setAvailable: (available: boolean | null) => void;
  reset: () => void;
}

export const useLanTransferStore = create<LanTransferState>((set) => ({
  room: null,
  roomToken: null,
  files: [],
  usedSize: 0,
  maxTotalSize: 0,
  fileCount: 0,
  available: null,

  setRoom: (room) =>
    set(() => ({
      room,
      usedSize: room?.used_size ?? 0,
      maxTotalSize: room?.max_total_size ?? 0,
      fileCount: room?.file_count ?? 0,
    })),

  setRoomToken: (roomToken) => set({ roomToken }),

  setFiles: (payload) =>
    set({
      files: payload.items,
      usedSize: payload.used_size,
      maxTotalSize: payload.max_total_size,
      fileCount: payload.file_count,
    }),

  setAvailable: (available) => set({ available }),

  reset: () =>
    set({
      room: null,
      roomToken: null,
      files: [],
      usedSize: 0,
      maxTotalSize: 0,
      fileCount: 0,
    }),
}));