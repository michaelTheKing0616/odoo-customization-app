"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import {
  api,
  ApiKeyRow,
  AuditLogRow,
  AuthStatus,
  getStoredApiKey,
  setStoredApiKey,
} from "@/lib/api";

export default function SettingsPage() {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [keys, setKeys] = useState<ApiKeyRow[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogRow[]>([]);
  const [localKey, setLocalKey] = useState("");
  const [newKeyName, setNewKeyName] = useState("operator");
  const [revealed, setRevealed] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const s = await api.authStatus();
    setStatus(s);
    setLocalKey(getStoredApiKey() ?? "");
    if (s.auth_enabled && getStoredApiKey()) {
      try {
        setKeys(await api.listApiKeys());
      } catch {
        setKeys([]);
      }
    } else {
      setKeys([]);
    }
    try {
      setAuditLogs(await api.listAuditLogs(30));
    } catch {
      setAuditLogs([]);
    }
  }

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, []);

  function onSaveLocal(e: FormEvent) {
    e.preventDefault();
    setStoredApiKey(localKey.trim() || null);
    setNotice(localKey.trim() ? "API key saved in this browser." : "API key cleared.");
    refresh().catch((err: Error) => setError(err.message));
  }

  async function onBootstrap() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const res = await api.bootstrapApiKey();
      setRevealed(res.api_key);
      setStoredApiKey(res.api_key);
      setLocalKey(res.api_key);
      setNotice(res.note);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bootstrap failed");
    } finally {
      setBusy(false);
    }
  }

  async function onCreateKey(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.createApiKey(newKeyName);
      setRevealed(res.api_key);
      setNotice(res.note);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create key failed");
    } finally {
      setBusy(false);
    }
  }

  async function onRevoke(id: string) {
    setBusy(true);
    setError(null);
    try {
      await api.revokeApiKey(id);
      setNotice("Key revoked.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Revoke failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(ellipse_at_top,_#3d2a38_0%,_#1a1218_50%,_#0c090b_100%)] px-6 py-10 text-[#f4eef2]">
      <div className="mx-auto max-w-2xl">
        <Link href="/connect" className="text-sm text-[#c9a9c0] hover:underline">
          ← Connections
        </Link>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[#faf6f9]">
          API settings
        </h1>
        <p className="mt-2 text-sm text-[#8f7a88]">
          Phase 7 — protect the customization API with an app API key (separate from Odoo
          credentials).
        </p>

        {error && <p className="mt-4 text-sm text-[#f0a8a0]">{error}</p>}
        {notice && <p className="mt-4 text-sm text-[#c9a9c0]">{notice}</p>}

        <section className="mt-8 border border-[#3d2a38] bg-[#0f1a16]/70 p-5 text-sm">
          <h2 className="font-[family-name:var(--font-display)] text-xl">Status</h2>
          {status ? (
            <ul className="mt-3 space-y-1 text-[#d4c4ce]">
              <li>
                Mode: <code className="text-[#c9a9c0]">{status.auth_mode}</code> · enabled={" "}
                {String(status.auth_enabled)}
              </li>
              <li>Active keys: {status.active_keys}</li>
              <li>Env APP_API_KEY configured: {String(status.env_key_configured)}</li>
              <li>Bootstrap available: {String(status.bootstrap_available)}</li>
            </ul>
          ) : (
            <p className="mt-3 text-[#8f7a88]">Loading…</p>
          )}
          {status?.bootstrap_available && (
            <button
              type="button"
              disabled={busy}
              onClick={onBootstrap}
              className="mt-4 h-10 bg-[#714B67] px-4 text-sm font-semibold text-white disabled:opacity-60"
            >
              Generate first API key
            </button>
          )}
        </section>

        <form
          onSubmit={onSaveLocal}
          className="mt-6 space-y-3 border border-[#3d2a38] bg-[#0f1a16]/70 p-5"
        >
          <h2 className="font-[family-name:var(--font-display)] text-xl">Browser key</h2>
          <p className="text-sm text-[#8f7a88]">
            Stored in localStorage and sent as{" "}
            <code className="text-[#c9a9c0]">Authorization: Bearer …</code>
          </p>
          <input
            value={localKey}
            onChange={(e) => setLocalKey(e.target.value)}
            className="w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono text-sm"
            placeholder="oc_…"
            autoComplete="off"
          />
          <button
            type="submit"
            className="h-10 border border-[#c9a9c0] px-4 text-sm text-[#c9a9c0]"
          >
            Save in browser
          </button>
        </form>

        {status?.auth_enabled && (
          <form
            onSubmit={onCreateKey}
            className="mt-6 space-y-3 border border-[#3d2a38] bg-[#0f1a16]/70 p-5"
          >
            <h2 className="font-[family-name:var(--font-display)] text-xl">Create key</h2>
            <input
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              className="w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-sm"
              placeholder="Key name"
            />
            <button
              type="submit"
              disabled={busy}
              className="h-10 bg-[#714B67] px-4 text-sm font-semibold text-white disabled:opacity-60"
            >
              Create
            </button>
          </form>
        )}

        {revealed && (
          <div className="mt-6 border border-[#5a3a2a] bg-[#1a100c] p-4">
            <p className="text-sm text-[#f0c090]">Copy now — shown once</p>
            <pre className="mt-2 overflow-auto text-xs text-[#faf6f9]">{revealed}</pre>
          </div>
        )}

        {keys.length > 0 && (
          <section className="mt-6">
            <h2 className="font-[family-name:var(--font-display)] text-xl">Keys</h2>
            <ul className="mt-3 space-y-2 text-sm">
              {keys.map((k) => (
                <li
                  key={k.id}
                  className="flex flex-wrap items-center justify-between gap-2 border border-[#1e2f29] px-3 py-2"
                >
                  <span>
                    {k.name}{" "}
                    <span className="font-mono text-[#c9a9c0]">{k.key_prefix}…</span>
                    {k.revoked_at ? (
                      <span className="text-[#f0a8a0]"> · revoked</span>
                    ) : null}
                  </span>
                  {!k.revoked_at && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => onRevoke(k.id)}
                      className="border border-[#f0a8a0] px-2 py-1 text-xs text-[#f0a8a0]"
                    >
                      Revoke
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="mt-6 border border-[#3d2a38] bg-[#0f1a16]/70 p-5">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-[family-name:var(--font-display)] text-xl">Audit log</h2>
            <button
              type="button"
              className="text-xs text-[#c9a9c0] hover:underline"
              onClick={() => refresh().catch((err: Error) => setError(err.message))}
            >
              Refresh
            </button>
          </div>
          <p className="mt-1 text-sm text-[#8f7a88]">
            Recent mutating API requests (POST/PUT/PATCH/DELETE).
          </p>
          {auditLogs.length === 0 ? (
            <p className="mt-3 text-sm text-[#8f7a88]">No entries yet.</p>
          ) : (
            <ul className="mt-3 max-h-80 space-y-1 overflow-auto font-mono text-xs text-[#d4c4ce]">
              {auditLogs.map((row) => (
                <li key={row.id} className="border-b border-[#1e2f29] py-1.5">
                  <span className="text-[#c9a9c0]">{row.method}</span> {row.path}{" "}
                  <span className="text-[#8f7a88]">→ {row.status_code}</span>
                  {row.duration_ms != null ? (
                    <span className="text-[#8f7a88]"> · {row.duration_ms}ms</span>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
