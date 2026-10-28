"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { register } from "@/lib/api/auth";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register({ email, username, password });
      router.push("/login");
    } catch (err) {
        const message = err instanceof Error ? err.message : "注册失败";
        setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-xl font-semibold">注册</h2>
      {error && <p className="text-sm text-red-500">{error}</p>}
      <input type="email" placeholder="邮箱" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full rounded border px-3 py-2" required />
      <input type="text" placeholder="用户名" value={username} onChange={(e) => setUsername(e.target.value)} className="w-full rounded border px-3 py-2" required />
      <input type="password" placeholder="密码" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full rounded border px-3 py-2" required />
      <button type="submit" disabled={loading} className="w-full rounded bg-blue-600 py-2 text-white hover:bg-blue-700 disabled:bg-blue-300">{loading ? "注册中..." : "注册"}</button>
    </form>
  );
}