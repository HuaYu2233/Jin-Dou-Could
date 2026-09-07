"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login } from "@/lib/api/auth";
// import { useAuthStore } from "@/stores/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    try {
      await login({ email, password });
      router.push("/dashboard");
    } catch (err) {
        const message = err instanceof Error ? err.message : "登录失败";
        setError(message);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-xl font-semibold">登录</h2>
      {error && <p className="text-sm text-red-500">{error}</p>}
      <input type="email" placeholder="邮箱" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full rounded border px-3 py-2" required />
      <input type="password" placeholder="密码" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full rounded border px-3 py-2" required />
      <button type="submit" className="w-full rounded bg-blue-600 py-2 text-white hover:bg-blue-700">登录</button>
      <div className="text-right">
        <Link href="/forgot-password" className="text-sm text-blue-600 hover:underline">忘记密码?</Link>
      </div>
    </form>
  );
}