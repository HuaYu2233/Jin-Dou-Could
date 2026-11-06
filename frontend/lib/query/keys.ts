export const queryKeys = {
  files: {
    all: ["files"] as const,
    list: (params: { category: string; page: number; folderId: string | null; keyword: string }) =>
      [...queryKeys.files.all, "list", params] as const,
  },
  shares: {
    all: ["shares"] as const,
    list: (page: number, pageSize: number) => [...queryKeys.shares.all, "list", page, pageSize] as const,
    info: (token: string) => [...queryKeys.shares.all, "info", token] as const,
  },
  admin: {
    all: ["admin"] as const,
    stats: () => [...queryKeys.admin.all, "stats"] as const,
    users: (page: number) => [...queryKeys.admin.all, "users", page] as const,
    backups: () => [...queryKeys.admin.all, "backups"] as const,
  },
  auth: {
    all: ["auth"] as const,
    me: () => [...queryKeys.auth.all, "me"] as const,
  },
};