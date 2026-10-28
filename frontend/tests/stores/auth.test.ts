import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "@/stores/auth";

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  });

  it("initial state is unauthenticated", () => {
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
  });

  it("setUser authenticates", () => {
    const mockUser = {
      id: "1",
      email: "test@example.com",
      username: "test",
      is_active: true,
      is_admin: false,
      avatar_key: null,
      security_question: null,
      created_at: "2025-01-01",
      storage_quota: 1073741824,
      used_storage: 0,
    };
    useAuthStore.getState().setUser(mockUser);
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.user).toEqual(mockUser);
  });

  it("logout clears state", () => {
    const mockUser = {
      id: "1",
      email: "test@example.com",
      username: "test",
      is_active: true,
      is_admin: false,
      avatar_key: null,
      security_question: null,
      created_at: "2025-01-01",
      storage_quota: 1073741824,
      used_storage: 0,
    };
    useAuthStore.getState().setUser(mockUser);
    useAuthStore.getState().logout();
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(state.error).toBeNull();
  });
});