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
    deploy: {
      all: () => [...queryKeys.admin.all, "deploy"] as const,
      status: () => [...queryKeys.admin.deploy.all(), "status"] as const,
      containers: () => [...queryKeys.admin.deploy.all(), "containers"] as const,
      versions: () => [...queryKeys.admin.deploy.all(), "versions"] as const,
      history: (limit: number) => [...queryKeys.admin.deploy.all(), "history", limit] as const,
      task: (taskId: string) => [...queryKeys.admin.deploy.all(), "task", taskId] as const,
    },
    envConfig: {
      all: () => [...queryKeys.admin.all, "envConfig"] as const,
      config: () => [...queryKeys.admin.envConfig.all(), "config"] as const,
    },
  },
  auth: {
    all: ["auth"] as const,
    me: () => [...queryKeys.auth.all, "me"] as const,
  },
  lanTransfer: {
    all: ["lanTransfer"] as const,
    room: (roomId: string) => [...queryKeys.lanTransfer.all, "room", roomId] as const,
  },
};