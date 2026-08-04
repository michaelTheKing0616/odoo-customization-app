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
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Card, PageHeader } from "@/components/ui/layout-primitives";

export default function SettingsPage() {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [keys, setKeys] = useState<ApiKeyRow[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogRow[]>([]);
  const [oauthIdentities, setOauthIdentities] = useState<
    Array<{ provider: string; email: string | null; created_at: string }>
  >([]);
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
    if (s.auth_mode === "accounts") {
      try {
        setOauthIdentities(await api.accountOAuthIdentities());
      } catch {
        setOauthIdentities([]);
      }
    } else {
      setOauthIdentities([]);
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

  async function onUnlinkOAuth(provider: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.accountOAuthUnlink(provider);
      setNotice(`Unlinked ${provider}.`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unlink failed");
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

  const auditColumns: DataTableColumn<AuditLogRow>[] = [
    {
      id: "method",
      header: "Method",
      accessor: (r) => <span className="text-accent">{r.method}</span>,
    },
    {
      id: "path",
      header: "Path",
      accessor: (r) => <span className="font-mono text-xs">{r.path}</span>,
    },
    {
      id: "status",
      header: "Status",
      accessor: (r) => r.status_code,
    },
    {
      id: "ms",
      header: "Ms",
      accessor: (r) => (r.duration_ms != null ? String(r.duration_ms) : "—"),
    },
  ];

  return (
    <div className="mx-auto max-w-2xl" data-testid="settings-page">
      <PageHeader
        title="API settings"
        description="Protect the customization API with an app API key (separate from Odoo credentials)."
      />

      {error ? <ErrorNotice message={error} className="mt-4" /> : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {notice}
        </Callout>
      ) : null}

      <Card className="mt-8 p-5">
        <h2 className="text-xl font-semibold text-ink">Status</h2>
        {status ? (
          <ul className="mt-3 space-y-1 text-sm text-muted">
            <li>
              Mode: <code className="text-ink">{status.auth_mode}</code> · enabled{" "}
              {String(status.auth_enabled)}
            </li>
            <li>Active keys: {status.active_keys}</li>
            <li>Env APP_API_KEY configured: {String(status.env_key_configured)}</li>
            <li>Bootstrap available: {String(status.bootstrap_available)}</li>
          </ul>
        ) : (
          <p className="mt-3 text-muted">Loading…</p>
        )}
        {status?.bootstrap_available ? (
          <Button
            type="button"
            variant="primary"
            className="mt-4"
            disabled={busy}
            loading={busy}
            onClick={onBootstrap}
          >
            Generate first API key
          </Button>
        ) : null}
      </Card>

      <Card className="mt-6 p-5">
        <form onSubmit={onSaveLocal} className="space-y-4">
          <h2 className="text-xl font-semibold text-ink">Browser key</h2>
          <p className="text-sm text-muted">
            Stored in localStorage and sent as Authorization: Bearer …
          </p>
          <Input
            value={localKey}
            onChange={(e) => setLocalKey(e.target.value)}
            placeholder="oc_…"
            autoComplete="off"
            className="font-mono text-sm"
          />
          <Button type="submit" variant="secondary">
            Save in browser
          </Button>
        </form>
      </Card>

      <Card className="mt-6 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xl font-semibold text-ink">Trust & safety</h2>
          <Link href="/settings/trust-safety" className="text-sm text-accent hover:underline">
            Open safety contract
          </Link>
        </div>
        <p className="mt-2 text-sm text-muted">
          Permission model, reversibility table, blast-radius limits, and incident playbook.
        </p>
      </Card>

      {status?.auth_enabled ? (
        <Card className="mt-6 p-5">
          <form onSubmit={onCreateKey} className="space-y-4">
            <h2 className="text-xl font-semibold text-ink">Create key</h2>
            <Input
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Key name"
            />
            <Button type="submit" variant="primary" disabled={busy} loading={busy}>
              Create
            </Button>
          </form>
        </Card>
      ) : null}

      {revealed ? (
        <Callout variant="warning" title="Copy now — shown once" className="mt-6">
          <pre className="mt-2 overflow-auto font-mono text-xs">{revealed}</pre>
        </Callout>
      ) : null}

      {keys.length > 0 ? (
        <section className="mt-6">
          <h2 className="text-xl font-semibold text-ink">Keys</h2>
          <ul className="mt-3 space-y-2">
            {keys.map((k) => (
              <li key={k.id}>
                <Card className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
                  <span>
                    {k.name}{" "}
                    <span className="font-mono text-muted">{k.key_prefix}…</span>
                    {k.revoked_at ? (
                      <Badge variant="danger" className="ml-2">
                        revoked
                      </Badge>
                    ) : null}
                  </span>
                  {!k.revoked_at ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={busy}
                      className="text-danger"
                      onClick={() => onRevoke(k.id)}
                    >
                      Revoke
                    </Button>
                  ) : null}
                </Card>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {status?.auth_mode === "accounts" && oauthIdentities.length > 0 ? (
        <Card className="mt-6 p-5">
          <h2 className="text-xl font-semibold text-ink">Linked sign-in providers</h2>
          <ul className="mt-3 space-y-2">
            {oauthIdentities.map((row) => (
              <li key={row.provider}>
                <Card className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
                  <span>
                    {row.provider}
                    {row.email ? <span className="ml-2 text-muted">{row.email}</span> : null}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={busy}
                    className="text-danger"
                    onClick={() => onUnlinkOAuth(row.provider)}
                  >
                    Unlink
                  </Button>
                </Card>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card className="mt-6 p-5">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-xl font-semibold text-ink">Audit log</h2>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => refresh().catch((err: Error) => setError(err.message))}
          >
            Refresh
          </Button>
        </div>
        <p className="mt-1 text-sm text-muted">
          Recent mutating API requests (POST/PUT/PATCH/DELETE).
        </p>
        <div className="mt-4">
          <DataTable
            columns={auditColumns}
            rows={auditLogs}
            rowKey={(r) => r.id}
            emptyState={<p className="text-sm text-muted">No entries yet.</p>}
          />
        </div>
      </Card>
    </div>
  );
}
