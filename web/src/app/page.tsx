"use client";

import { useCallback, useEffect, useState } from "react";
import { LoginForm } from "@/components/LoginForm";
import { MinutesApp } from "@/components/MinutesApp";

type Me = {
  authenticated: boolean;
  hasPassword: boolean;
  hasApiKey: boolean;
};

export default function HomePage() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const res = await fetch("/api/me");
    const data = (await res.json()) as Me;
    setMe(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    await refresh();
  }

  if (loading || !me) {
    return (
      <main className="page">
        <p className="caption">読み込み中…</p>
      </main>
    );
  }

  return (
    <main className="page">
      {me.authenticated ? (
        <MinutesApp apiConfigured={me.hasApiKey} onLogout={logout} />
      ) : (
        <LoginForm
          passwordConfigured={me.hasPassword}
          onSuccess={() => void refresh()}
        />
      )}
    </main>
  );
}
