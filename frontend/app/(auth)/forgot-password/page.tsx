"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { forgotPassword, resetPassword, getSecurityQuestion, resetPasswordBySecurity } from "@/lib/api/auth";
import styles from "../auth.module.css";

type Tab = "email" | "security";

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("email");

  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [sending, setSending] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [sent, setSent] = useState(false);

  const [secEmail, setSecEmail] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [secNewPassword, setSecNewPassword] = useState("");
  const [secError, setSecError] = useState("");
  const [secInfo, setSecInfo] = useState("");
  const [loadingQ, setLoadingQ] = useState(false);
  const [resettingSec, setResettingSec] = useState(false);
  const [questionLoaded, setQuestionLoaded] = useState(false);

  function switchTab(t: Tab) {
    setTab(t);
    setError("");
    setInfo("");
    setSecError("");
    setSecInfo("");
  }

  async function handleSendCode(e: FormEvent) {
    e.preventDefault();
    setError("");
    setInfo("");
    setSending(true);
    try {
      await forgotPassword(email);
      setSent(true);
      setInfo("验证码已发送，请查收邮件");
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
    } finally {
      setSending(false);
    }
  }

  async function handleReset(e: FormEvent) {
    e.preventDefault();
    setError("");
    setInfo("");
    setResetting(true);
    try {
      await resetPassword(email, code, newPassword);
      setInfo("密码重置成功，即将跳转登录");
      setTimeout(() => router.push("/login"), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "重置失败");
    } finally {
      setResetting(false);
    }
  }

  async function handleLoadQuestion(e: FormEvent) {
    e.preventDefault();
    setSecError("");
    setSecInfo("");
    setQuestion("");
    setQuestionLoaded(false);
    setLoadingQ(true);
    try {
      const res = await getSecurityQuestion(secEmail);
      setQuestion(res.question);
      setQuestionLoaded(true);
    } catch (err) {
      setSecError(err instanceof Error ? err.message : "获取失败");
    } finally {
      setLoadingQ(false);
    }
  }

  async function handleResetBySecurity(e: FormEvent) {
    e.preventDefault();
    setSecError("");
    setSecInfo("");
    setResettingSec(true);
    try {
      await resetPasswordBySecurity(secEmail, answer, secNewPassword);
      setSecInfo("密码重置成功，即将跳转登录");
      setTimeout(() => router.push("/login"), 1500);
    } catch (err) {
      setSecError(err instanceof Error ? err.message : "重置失败");
    } finally {
      setResettingSec(false);
    }
  }

  return (
    <div className={styles.form}>
      <h2 className={styles.title}>找回密码</h2>

      <div className={styles.tabs}>
        <button
          type="button"
          onClick={() => switchTab("email")}
          className={`${styles.tabBtn} ${tab === "email" ? styles.tabBtnActive : ""}`}
        >
          邮箱验证码
        </button>
        <button
          type="button"
          onClick={() => switchTab("security")}
          className={`${styles.tabBtn} ${tab === "security" ? styles.tabBtnActive : ""}`}
        >
          密保问题
        </button>
      </div>

      {tab === "email" ? (
        <form onSubmit={sent ? handleReset : handleSendCode} className={styles.form}>
          {error && <p className={styles.alertError}>{error}</p>}
          {info && <p className={styles.alertSuccess}>{info}</p>}

          <input
            type="email"
            placeholder="注册邮箱"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={styles.input}
            required
            disabled={sent}
          />

          {sent && (
            <>
              <input
                type="text"
                placeholder="验证码"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className={styles.input}
                required
              />
              <input
                type="password"
                placeholder="新密码（至少 6 位）"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className={styles.input}
                required
                minLength={6}
              />
            </>
          )}

          {!sent ? (
            <button type="submit" disabled={sending} className={styles.submitBtn}>
              {sending ? "发送中..." : "发送验证码"}
            </button>
          ) : (
            <button type="submit" disabled={resetting} className={styles.submitBtn}>
              {resetting ? "重置中..." : "重置密码"}
            </button>
          )}
        </form>
      ) : (
        <div className={styles.form}>
          {secError && <p className={styles.alertError}>{secError}</p>}
          {secInfo && <p className={styles.alertSuccess}>{secInfo}</p>}

          {!questionLoaded ? (
            <form onSubmit={handleLoadQuestion} className={styles.form}>
              <input
                type="email"
                placeholder="注册邮箱"
                value={secEmail}
                onChange={(e) => setSecEmail(e.target.value)}
                className={styles.input}
                required
              />
              <button type="submit" disabled={loadingQ} className={styles.submitBtn}>
                {loadingQ ? "查询中..." : "获取密保问题"}
              </button>
            </form>
          ) : (
            <form onSubmit={handleResetBySecurity} className={styles.form}>
              <div className={styles.questionBox}>
                <span className={styles.questionLabel}>密保问题：</span>
                <span className={styles.questionValue}>{question}</span>
              </div>
              <input
                type="text"
                placeholder="密保答案"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                className={styles.input}
                required
              />
              <input
                type="password"
                placeholder="新密码（至少 6 位）"
                value={secNewPassword}
                onChange={(e) => setSecNewPassword(e.target.value)}
                className={styles.input}
                required
                minLength={6}
              />
              <button type="submit" disabled={resettingSec} className={styles.submitBtn}>
                {resettingSec ? "重置中..." : "重置密码"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setQuestionLoaded(false);
                  setQuestion("");
                  setAnswer("");
                  setSecNewPassword("");
                }}
                className={styles.ghostBtn}
              >
                重新输入邮箱
              </button>
            </form>
          )}
        </div>
      )}

      <div className={styles.centerLinkRow}>
        <Link href="/login" className={styles.link}>
          返回登录
        </Link>
      </div>
    </div>
  );
}