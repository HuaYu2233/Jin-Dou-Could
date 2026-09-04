// /Users/zero/project/JinDou-Cloud/frontend/app/dashboard/types.ts
export type CategoryId = "all" | "image" | "document" | "video" | "audio" | "other" | "trash" | "shares" | "transfers";

export type ViewMode = "list" | "grid";

export interface BreadcrumbItem {
  id: string | null;
  name: string;
  path: string;
}

export interface StorageInfo {
  used: number;
  total: number;
}