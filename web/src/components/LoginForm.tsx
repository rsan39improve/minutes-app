"use client";

import { FormEvent, useState } from "react";

type Props = {
  onSuccess: () => void;
  passwordConfigured: boolean;
};

export function LoginForm({ onSuccess, passwordConfigured }: Props) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "ログインに失敗しました。");
        return;
      }
      onSuccess();
    } catch {
      setError("通信エラーが発生しました。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel">
      <header className="topbar">
        <div className="brand-row">
          <h1 className="brand">議事録自動作成ツール</h1>
          <span className="badge">Internal</span>
        </div>
      </header>
      <p className="caption">社内限定ツールです。パスワードを入力してください。</p>
      <hr className="rule" />

      {!passwordConfigured ? (
        <p className="warn">
          管理者設定（アクセスパスワード）が未完了のため、現在使用できません。
        </p>
      ) : (
        <form onSubmit={onSubmit} className="stack">
          <label className="label">
            パスワード
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input"
              autoComplete="current-password"
              required
            />
          </label>
          {error ? <p className="error">{error}</p> : null}
          <button type="submit" className="cta" disabled={loading}>
            {loading ? "確認中…" : "入室する"}
          </button>
        </form>
      )}
    </div>
  );
}
