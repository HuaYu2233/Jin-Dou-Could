import { client } from "./client";

export interface LoginData { email: string; password: string; }
export interface RegisterData { email: string; username: string; password: string; }
export interface User { id: string; email: string; username: string; is_active: boolean; created_at: string; storage_quota: number; used_storage: number; }
export interface TokenResponse { access_token: string; token_type: string; }

export async function login(data: LoginData): Promise<TokenResponse> {
  return client<TokenResponse>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(data) });
}

export async function register(data: RegisterData): Promise<User> {
  return client<User>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(data) });
}

export async function getMe(): Promise<User> {
  return client<User>("/api/v1/users/me");
}