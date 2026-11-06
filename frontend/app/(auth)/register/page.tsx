"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { register } from "@/lib/api/auth";
import styles from "../auth.module.css";

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
    <form onSubmit={handleSubmit} className={styles.form}>
      <h2 className={styles.title}>注册</h2>
      {error && <p className={styles.alertError}>{error}</p>}
      <input
        type="email"
        placeholder="邮箱"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className={styles.input}
        required
      />
      <input
        type="text"
        placeholder="用户名"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        className={styles.input}
        required
      />
      <input
        type="password"
        placeholder="密码"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className={styles.input}
        required
      />
      <button type="submit" disabled={loading} className={styles.submitBtn}>
        {loading ? "注册中..." : "注册"}
      </button>
    </form>
  );
}