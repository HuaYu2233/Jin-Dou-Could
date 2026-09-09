"use client";

import { useState, useRef } from "react";
import { useAuthStore } from "@/stores/auth";
import Avatar from "../dashboard/components/Avatar";
import AvatarEditor from "../dashboard/components/AvatarEditor";
import PageHeader from "../admin/components/PageHeader";
import { updateProfile, changePassword, uploadAvatar, setSecurityQuestion } from "@/lib/api/auth";
import { useTranslation } from "@/lib/i18n";
import styles from "./page.module.css";

export default function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const { t } = useTranslation();

  const [username, setUsername] = useState(user?.username ?? "");
  const [secQuestion, setSecQuestion] = useState(user?.security_question ?? "");
  const [prevUser, setPrevUser] = useState(user);
  if (user !== prevUser) {
    setPrevUser(user);
    setUsername(user?.username ?? "");
    setSecQuestion(user?.security_question ?? "");
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
  const [secAnswer, setSecAnswer] = useState("");
  const [savingSec, setSavingSec] = useState(false);
  const [secMsg, setSecMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  if (!user) return null;

  async function handleSaveName() {
    setSavingName(true);
    setNameMsg(null);
    try {
      const updated = await updateProfile(username);
      setUser(updated);
      setNameMsg({ ok: true, text: t("profile.editUsername.updated") });
    } catch (err) {
      setNameMsg({ ok: false, text: err instanceof Error ? err.message : t("profile.editUsername.updateFailed") });
    } finally {
      setSavingName(false);
    }
  }

  async function handleChangePwd() {
    setPwdMsg(null);
    if (newPwd !== confirmPwd) {
      setPwdMsg({ ok: false, text: t("profile.editPassword.mismatch") });
      return;
    }
    setSavingPwd(true);
    try {
      await changePassword(oldPwd, newPwd);
      setPwdMsg({ ok: true, text: t("profile.editPassword.updated") });
      setOldPwd("");
      setNewPwd("");
      setConfirmPwd("");
    } catch (err) {
      setPwdMsg({ ok: false, text: err instanceof Error ? err.message : t("profile.editPassword.updateFailed") });
    } finally {
      setSavingPwd(false);
    }
  }

  async function handleSaveSecurity() {
    setSavingSec(true);
    setSecMsg(null);
    try {
      const updated = await setSecurityQuestion(secQuestion, secAnswer);
      setUser(updated);
      setSecAnswer("");
      setSecMsg({ ok: true, text: t("profile.security.updated") });
    } catch (err) {
      setSecMsg({ ok: false, text: err instanceof Error ? err.message : t("profile.security.updateFailed") });
    } finally {
      setSavingSec(false);
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
      alert(err instanceof Error ? err.message : t("profile.uploadFailed"));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className={styles.page}>
      <PageHeader title={t("profile.title")} subtitle={t("profile.subtitle")} />

      <div className={styles.avatarSection}>
        <Avatar
          userId={user.id}
          username={user.username}
          avatarKey={user.avatar_key}
          size="lg"
        />
        <div className={styles.avatarInfo}>
          <div className={styles.avatarName}>{user.username}</div>
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
          {uploading ? t("profile.uploading") : t("profile.changeAvatar")}
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
        <h2 className={styles.sectionTitle}>{t("profile.editUsername.title")}</h2>
        <div className={styles.field}>
          <label className={styles.label}>{t("profile.editUsername.label")}</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className={styles.input}
          />
        </div>
        <div className={styles.actions}>
          <button className={styles.saveBtn} onClick={handleSaveName} disabled={savingName}>
            {savingName ? t("common.saving") : t("common.save")}
          </button>
        </div>
        {nameMsg && (
          <div className={`${styles.message} ${nameMsg.ok ? styles.messageOk : styles.messageErr}`}>
            {nameMsg.text}
          </div>
        )}
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>{t("profile.editPassword.title")}</h2>
        <div className={styles.field}>
          <label className={styles.label}>{t("profile.editPassword.oldLabel")}</label>
          <input
            type="password"
            value={oldPwd}
            onChange={(e) => setOldPwd(e.target.value)}
            className={styles.input}
          />
        </div>
        <div className={styles.field}>
          <label className={styles.label}>{t("profile.editPassword.newLabel")}</label>
          <input
            type="password"
            value={newPwd}
            onChange={(e) => setNewPwd(e.target.value)}
            className={styles.input}
          />
        </div>
        <div className={styles.field}>
          <label className={styles.label}>{t("profile.editPassword.confirmLabel")}</label>
          <input
            type="password"
            value={confirmPwd}
            onChange={(e) => setConfirmPwd(e.target.value)}
            className={styles.input}
          />
        </div>
        <div className={styles.actions}>
          <button className={styles.saveBtn} onClick={handleChangePwd} disabled={savingPwd}>
            {savingPwd ? t("common.saving") : t("common.save")}
          </button>
        </div>
        {pwdMsg && (
          <div className={`${styles.message} ${pwdMsg.ok ? styles.messageOk : styles.messageErr}`}>
            {pwdMsg.text}
          </div>
        )}
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>{t("profile.security.title")}</h2>
        <p className={styles.label} style={{ marginBottom: 12 }}>
          {t("profile.security.desc")}
        </p>
        <div className={styles.field}>
          <label className={styles.label}>{t("profile.security.questionLabel")}</label>
          <input
            type="text"
            value={secQuestion}
            onChange={(e) => setSecQuestion(e.target.value)}
            className={styles.input}
            placeholder={t("profile.security.questionPlaceholder")}
          />
        </div>
        <div className={styles.field}>
          <label className={styles.label}>{t("profile.security.answerLabel")}</label>
          <input
            type="text"
            value={secAnswer}
            onChange={(e) => setSecAnswer(e.target.value)}
            className={styles.input}
            placeholder={user.security_question ? t("profile.security.answerPlaceholder.change") : t("profile.security.answerPlaceholder.set")}
          />
        </div>
        <div className={styles.actions}>
          <button className={styles.saveBtn} onClick={handleSaveSecurity} disabled={savingSec}>
            {savingSec ? t("common.saving") : t("common.save")}
          </button>
        </div>
        {secMsg && (
          <div className={`${styles.message} ${secMsg.ok ? styles.messageOk : styles.messageErr}`}>
            {secMsg.text}
          </div>
        )}
      </div>
    </div>
  );
}