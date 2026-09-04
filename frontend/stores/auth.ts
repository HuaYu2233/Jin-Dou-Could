import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { User } from "@/lib/api/auth";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  isAuthenticated: boolean;

  fetchMe: () => Promise<void>;
  setUser: (user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isLoading: false,
      error: null,
      isAuthenticated: false,

      async fetchMe() {
        set({ isLoading: true, error: null });
        try {
          const { getMe } = await import("@/lib/api/auth");
          const user = await getMe();
          set({ user, isAuthenticated: true, isLoading: false });
        } catch (err) {
          set({
            user: null,
            isAuthenticated: false,
            isLoading: false,
            error: err instanceof Error ? err.message : "获取用户信息失败",
          });
        }
      },

      setUser(user) {
        set({ user, isAuthenticated: true, error: null });
      },

      logout() {
        set({ user: null, isAuthenticated: false, error: null });
      },
    }),
    {
      name: "auth-storage",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);