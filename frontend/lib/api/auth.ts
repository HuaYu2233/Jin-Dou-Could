import { client } from "./client";
import { API_BASE_URL } from "@/lib/config";

export interface LoginData { email: string; password: string; }
export interface RegisterData { email: string; username: string; password: string; }
export interface User { id: string; email: string; username: string; is_active: boolean; is_admin: boolean; avatar_key: string | null; security_question: string | null; created_at: string; storage_quota: number; used_storage: number; }

export async function login(data: LoginData): Promise<{ detail: string }> {
  return client<{ detail: string }>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(data) });
}

export async function register(data: RegisterData): Promise<User> {
  return client<User>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(data) });
}

export async function forgotPassword(email: string): Promise<{ detail: string }> {
  return client<{ detail: string }>("/api/v1/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(
  email: string,
  code: string,
  newPassword: string
): Promise<{ detail: string }> {
  return client<{ detail: string }>("/api/v1/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ email, code, new_password: newPassword }),
  });
}

export async function setSecurityQuestion(question: string, answer: string): Promise<User> {
  return client<User>("/api/v1/users/me/security-question", {
    method: "PATCH",
    body: JSON.stringify({ security_question: question, security_answer: answer }),
  });
}

export async function getSecurityQuestion(email: string): Promise<{ question: string }> {
  return client<{ question: string }>("/api/v1/auth/security-question", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function resetPasswordBySecurity(
  email: string,
  answer: string,
  newPassword: string
): Promise<{ detail: string }> {
  return client<{ detail: string }>("/api/v1/auth/reset-password-by-security", {
    method: "POST",
    body: JSON.stringify({ email, answer, new_password: newPassword }),
  });
}

export async function getMe(): Promise<User> {
  return client<User>("/api/v1/users/me");
}

export async function updateProfile(username: string): Promise<User> {
  return client<User>("/api/v1/users/me/profile", {
    method: "PATCH",
    body: JSON.stringify({ username }),
  });
}

export async function changePassword(oldPassword: string, newPassword: string): Promise<User> {
  return client<User>("/api/v1/users/me/password", {
    method: "PATCH",
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  });
}

export async function uploadAvatar(blob: Blob): Promise<User> {
  const formData = new FormData();
  formData.append("file", blob, "avatar.jpg");
  return client<User>("/api/v1/users/me/avatar", {
    method: "POST",
    body: formData,
  });
}

export function getAvatarUrl(userId: string): string {
  return `${API_BASE_URL}/api/v1/users/me/avatar?_t=${userId}`;
}