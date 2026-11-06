"use client";

import { useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { login } from "@/lib/api/auth";
import { useAuthStore } from "@/stores/auth";
import styles from "../auth.module.css";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const infoMsg = searchParams.get("auth_expired") ? "登录已过期，请重新登录" : "";

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login({ email, password });
      await useAuthStore.getState().fetchMe();
      const redirect = searchParams.get("redirect");
      router.push(redirect || "/dashboard");
    } catch (err) {
      const message = err instanceof Error ? err.message : "登录失败";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className={styles.form}>
      <h2 className={styles.title}>登录</h2>
      {infoMsg && <p className={styles.alertInfo}>{infoMsg}</p>}
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
        type="password"
        placeholder="密码"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className={styles.input}
        required
      />
      <button type="submit" disabled={loading} className={styles.submitBtn}>
        {loading ? "登录中..." : "登录"}
      </button>
      <div className={styles.linkRow}>
        <Link href="/forgot-password" className={styles.link}>
          忘记密码?
        </Link>
      </div>
    </form>
  );
}