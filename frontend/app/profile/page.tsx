"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth";
import Avatar from "../dashboard/components/Avatar";
import AvatarEditor from "../dashboard/components/AvatarEditor";
import { updateProfile, changePassword, uploadAvatar } from "@/lib/api/auth";
import styles from "./page.module.css";

export default function ProfilePage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) router.replace("/login");
  }, [isAuthenticated, router]);

  const [username, setUsername] = useState(user?.username ?? "");
  const [prevUser, setPrevUser] = useState(user);
  if (user !== prevUser) {
    setPrevUser(user);
    setUsername(user?.username ?? "");
  }
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [savingPwd, setSavingPwd] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [editingFile, setEditingFile] = useState<File | null>(null);
  const [nameMsg, setNameMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [pwdMsg, setPwdMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  if (!user) return null;

  async function handleSaveName() {
    setSavingName(true);
    setNameMsg(null);
    try {
      const updated = await updateProfile(username);
      setUser(updated);
      setNameMsg({ ok: true, text: "用户名已更新" });
    } catch (err) {
      setNameMsg({ ok: false, text: err instanceof Error ? err.message : "更新失败" });
    } finally {
      setSavingName(false);
    }
  }

  async function handleChangePwd() {
    setPwdMsg(null);
    if (newPwd !== confirmPwd) {
      setPwdMsg({ ok: false, text: "两次输入的新密码不一致" });
      return;
    }
    setSavingPwd(true);
    try {
      await changePassword(oldPwd, newPwd);
      setPwdMsg({ ok: true, text: "密码已更新" });
      setOldPwd("");
      setNewPwd("");
      setConfirmPwd("");
    } catch (err) {
      setPwdMsg({ ok: false, text: err instanceof Error ? err.message : "更新失败" });
    } finally {
      setSavingPwd(false);
    }
  }

  function handlePickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setEditingFile(file);
    if (fileRef.current) fileRef.current.value = "";
  }

  async function handleConfirmAvatar(blob: Blob) {
    setUploading(true);
    try {
      const updated = await uploadAvatar(blob);
      setUser(updated);
      setEditingFile(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "上传失败");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>用户中心</h1>
        <p className={styles.subtitle}>管理你的个人信息与安全设置</p>
      </div>

      <div className={styles.avatarSection}>
        <Avatar
          userId={user.id}
          username={user.username}
          avatarKey={user.avatar_key}
          size="lg"
        />
        <div className={styles.avatarInfo}>
          <div className={styles.username}>{user.username}</div>
          <div className={styles.avatarEmail}>{user.email}</div>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          onChange={handlePickFile}
          style={{ display: "none" }}
        />
        <button
          className={styles.uploadBtn}
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? "上传中..." : "更换头像"}
        </button>
      </div>

      {editingFile && (
        <AvatarEditor
          file={editingFile}
          onConfirm={handleConfirmAvatar}
          onClose={() => !uploading && setEditingFile(null)}
        />
      )}

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>修改用户名</h2>
        <div className={styles.field}>
          <label className={styles.label}>用户名</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className={styles.input}
          />
        </div>
        <div className={styles.actions}>
          <button className={styles.saveBtn} onClick={handleSaveName} disabled={savingName}>
            {savingName ? "保存中..." : "保存"}
          </button>
        </div>
        {nameMsg && (
          <div className={`${styles.message} ${nameMsg.ok ? styles.messageOk : styles.messageErr}`}>
            {nameMsg.text}
          </div>
        )}
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>修改密码</h2>
        <div className={styles.field}>
          <label className={styles.label}>原密码</label>
          <input
            type="password"
            value={oldPwd}
            onChange={(e) => setOldPwd(e.target.value)}
            className={styles.input}
          />
        </div>
        <div className={styles.field}>
          <label className={styles.label}>新密码</label>
          <input
            type="password"
            value={newPwd}
            onChange={(e) => setNewPwd(e.target.value)}
            className={styles.input}
          />
        </div>
        <div className={styles.field}>
          <label className={styles.label}>确认新密码</label>
          <input
            type="password"
            value={confirmPwd}
            onChange={(e) => setConfirmPwd(e.target.value)}
            className={styles.input}
          />
        </div>
        <div className={styles.actions}>
          <button className={styles.saveBtn} onClick={handleChangePwd} disabled={savingPwd}>
            {savingPwd ? "保存中..." : "保存"}
          </button>
        </div>
        {pwdMsg && (
          <div className={`${styles.message} ${pwdMsg.ok ? styles.messageOk : styles.messageErr}`}>
            {pwdMsg.text}
          </div>
        )}
      </div>

      <Link href="/dashboard" className={styles.backLink}>← 返回网盘</Link>
    </div>
  );
}