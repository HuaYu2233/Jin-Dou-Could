"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { forgotPassword, resetPassword, getSecurityQuestion, resetPasswordBySecurity } from "@/lib/api/auth";

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
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">找回密码</h2>

      <div className="flex gap-2 border-b border-gray-200">
        <button
          type="button"
          onClick={() => switchTab("email")}
          className={`px-3 py-1.5 text-sm font-medium border-b-2 -mb-px ${
            tab === "email" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500"
          }`}
        >
          邮箱验证码
        </button>
        <button
          type="button"
          onClick={() => switchTab("security")}
          className={`px-3 py-1.5 text-sm font-medium border-b-2 -mb-px ${
            tab === "security" ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500"
          }`}
        >
          密保问题
        </button>
      </div>

      {tab === "email" ? (
      <form onSubmit={sent ? handleReset : handleSendCode} className="space-y-4">
      {error && <p className="text-sm text-red-500">{error}</p>}
      {info && <p className="text-sm text-green-600">{info}</p>}

      <input
        type="email"
        placeholder="注册邮箱"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="w-full rounded border px-3 py-2"
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
            className="w-full rounded border px-3 py-2"
            required
          />
          <input
            type="password"
            placeholder="新密码（至少 6 位）"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="w-full rounded border px-3 py-2"
            required
            minLength={6}
          />
        </>
      )}

      {!sent ? (
        <button
          type="submit"
          disabled={sending}
          className="w-full rounded bg-blue-600 py-2 text-white hover:bg-blue-700 disabled:bg-blue-300"
        >
          {sending ? "发送中..." : "发送验证码"}
        </button>
      ) : (
        <button
          type="submit"
          disabled={resetting}
          className="w-full rounded bg-blue-600 py-2 text-white hover:bg-blue-700 disabled:bg-blue-300"
        >
          {resetting ? "重置中..." : "重置密码"}
        </button>
      )}
      </form>
      ) : (
        <div className="space-y-4">
          {secError && <p className="text-sm text-red-500">{secError}</p>}
          {secInfo && <p className="text-sm text-green-600">{secInfo}</p>}

          {!questionLoaded ? (
            <form onSubmit={handleLoadQuestion} className="space-y-4">
              <input
                type="email"
                placeholder="注册邮箱"
                value={secEmail}
                onChange={(e) => setSecEmail(e.target.value)}
                className="w-full rounded border px-3 py-2"
                required
              />
              <button
                type="submit"
                disabled={loadingQ}
                className="w-full rounded bg-blue-600 py-2 text-white hover:bg-blue-700 disabled:bg-blue-300"
              >
                {loadingQ ? "查询中..." : "获取密保问题"}
              </button>
            </form>
          ) : (
            <form onSubmit={handleResetBySecurity} className="space-y-4">
              <div className="rounded border border-gray-200 bg-gray-50 px-3 py-2 text-sm">
                <span className="text-gray-500">密保问题：</span>
                <span className="text-gray-800">{question}</span>
              </div>
              <input
                type="text"
                placeholder="密保答案"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                className="w-full rounded border px-3 py-2"
                required
              />
              <input
                type="password"
                placeholder="新密码（至少 6 位）"
                value={secNewPassword}
                onChange={(e) => setSecNewPassword(e.target.value)}
                className="w-full rounded border px-3 py-2"
                required
                minLength={6}
              />
              <button
                type="submit"
                disabled={resettingSec}
                className="w-full rounded bg-blue-600 py-2 text-white hover:bg-blue-700 disabled:bg-blue-300"
              >
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
                className="w-full text-center text-sm text-gray-500 hover:underline"
              >
                重新输入邮箱
              </button>
            </form>
          )}
        </div>
      )}

      <div className="text-center">
        <Link href="/login" className="text-sm text-blue-600 hover:underline">
          返回登录
        </Link>
      </div>
    </div>
  );
}