"use client";

import { DensityPicker, DisplayNameField, OdooDimToggle, ThemePicker, ReadingComfortToggle, SoundToggle } from "@/components/settings/SoundToggle";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
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
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui/layout-primitives";
import { SettingsErrorNotice } from "@/components/settings/SettingsErrorNotice";
import { AiSavingsCard } from "@/components/settings/AiSavingsCard";
import { SettingsStageRail } from "@/components/settings/SettingsStageRail";
import { SettingsStateGuide } from "@/components/settings/SettingsStateGuide";
import {
  BOOTSTRAP_CTA,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  REVOKE_PHRASE,
  SAVE_CTA,
  bootstrapSettingsGuide,
  emptySettingsGuide,
  idleSettingsGuide,
  revealedSettingsGuide,
  savedBrowserGuide,
  settingsHonestyGuide,
  settingsStepFromState,
  type SettingsErrorContext,
} from "@/lib/settingsScreen";
import "@/components/settings/settings-operate.css";

const AUDIT_EMPTY = (
  <EmptyState
    title="No audit entries yet"
    description="Each POST, PUT, PATCH, or DELETE request to this API appears here with its status and duration."
  />
);

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
  const [errorContext, setErrorContext] = useState<SettingsErrorContext>("load");
  const [saveGuideCleared, setSaveGuideCleared] = useState<boolean | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [keysListed, setKeysListed] = useState(false);
  const [auditHydrated, setAuditHydrated] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<ApiKeyRow | null>(null);

  async function refresh() {
    const s = await api.authStatus();
    setStatus(s);
    setLocalKey(getStoredApiKey() ?? "");
    setKeysListed(Boolean(s.auth_enabled && getStoredApiKey()));
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
    } finally {
      setAuditHydrated(true);
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
    refresh()
      .catch((err: Error) => {
        setErrorContext("load");
        setError(err.message);
      })
      .finally(() => setAuditHydrated(true));
  }, []);

  function onSaveLocal(e: FormEvent) {
    e.preventDefault();
    try {
      const trimmed = localKey.trim();
      setStoredApiKey(trimmed || null);
      setSaveGuideCleared(!trimmed);
      setError(null);
      refresh().catch((err: Error) => {
        setErrorContext("load");
        setError(err.message);
      });
    } catch (err) {
      setErrorContext("save");
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  async function onBootstrap() {
    setBusy(true);
    setError(null);
    setSaveGuideCleared(null);
    try {
      const res = await api.bootstrapApiKey();
      setRevealed(res.api_key);
      setStoredApiKey(res.api_key);
      setLocalKey(res.api_key);
      setCopied(false);
      await refresh();
    } catch (err) {
      setErrorContext("bootstrap");
      setError(err instanceof Error ? err.message : "Bootstrap failed");
    } finally {
      setBusy(false);
    }
  }

  async function onCreateKey(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaveGuideCleared(null);
    try {
      const res = await api.createApiKey(newKeyName);
      setRevealed(res.api_key);
      setCopied(false);
      await refresh();
    } catch (err) {
      setErrorContext("create");
      setError(err instanceof Error ? err.message : "Create key failed");
    } finally {
      setBusy(false);
    }
  }

  async function onUnlinkOAuth(provider: string) {
    setBusy(true);
    setError(null);
    try {
      await api.accountOAuthUnlink(provider);
      await refresh();
    } catch (err) {
      setErrorContext("unlink");
      setError(err instanceof Error ? err.message : "Unlink failed");
    } finally {
      setBusy(false);
    }
  }

  async function onRevokeConfirm() {
    if (!revokeTarget) return;
    setBusy(true);
    setError(null);
    try {
      await api.revokeApiKey(revokeTarget.id);
      setRevokeTarget(null);
      await refresh();
    } catch (err) {
      setErrorContext("revoke");
      setError(err instanceof Error ? err.message : "Revoke failed");
    } finally {
      setBusy(false);
    }
  }

  async function onCopyRevealed() {
    if (!revealed) return;
    try {
      await navigator.clipboard.writeText(revealed);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const step = settingsStepFromState({
    hasStatus: Boolean(status),
    keysListed,
    keyCount: keys.filter((k) => !k.revoked_at).length,
    revealed: Boolean(revealed),
    auditHydrated,
  });

  const contextualGuide = useMemo(() => {
    if (revealed) return { tone: "warning" as const, testId: "settings-revealed-guide", guide: revealedSettingsGuide() };
    if (status?.bootstrap_available) {
      return { tone: "accent" as const, testId: "settings-bootstrap-guide", guide: bootstrapSettingsGuide() };
    }
    if (keysListed && keys.length === 0 && status?.auth_enabled) {
      return { tone: "accent" as const, testId: "settings-empty-guide", guide: emptySettingsGuide() };
    }
    if (status) {
      return { tone: "accent" as const, testId: "settings-idle-guide", guide: idleSettingsGuide() };
    }
    return null;
  }, [revealed, status, keysListed, keys.length]);

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
      accessor: (r) => (r.duration_ms != null ? String(r.duration_ms) : "-"),
    },
  ];

  const showCreate = Boolean(status?.auth_enabled && !status.bootstrap_available);

  return (
    <div className="settings-operate" data-testid="settings-page">
      <PageHeader title={PAGE_TITLE} description={PAGE_DESCRIPTION} />

      <SettingsStageRail step={step} />

      <SettingsStateGuide
        className="mt-4"
        tone="warning"
        testId="settings-honesty"
        guide={settingsHonestyGuide()}
      />

      {error ? (
        <SettingsErrorNotice
          className="mt-4"
          message={error}
          context={errorContext}
          onDismiss={() => setError(null)}
          onRetry={() => {
            setError(null);
            refresh().catch((err: Error) => {
              setErrorContext("load");
              setError(err.message);
            });
          }}
        />
      ) : null}

      {saveGuideCleared != null ? (
        <SettingsStateGuide
          className="mt-4"
          tone="accent"
          testId="settings-saved-guide"
          guide={savedBrowserGuide(saveGuideCleared)}
          live
        />
      ) : null}

      {contextualGuide ? (
        <SettingsStateGuide
          className="mt-4"
          tone={contextualGuide.tone}
          testId={contextualGuide.testId}
          guide={contextualGuide.guide}
        />
      ) : null}

      {busy ? (
        <div className="stg-busy" role="status" aria-live="polite" data-testid="settings-busy">
          <span className="sr-only">Working on settings.</span>
          <span aria-hidden />
        </div>
      ) : null}

      <AiSavingsCard />

      <section className="stg-panel" data-testid="settings-status-panel">
        <h2 className="stg-panel-title">Status</h2>
        <p className="stg-panel-sub">How apps sign in to Ingenium, and whether the first key can still be created.</p>
        {status ? (
          <ul className="stg-status-list">
            <li>
              Sign-in: <code>{status.auth_mode}</code> · {status.auth_enabled ? "required" : "not required"}
            </li>
            <li>Keys in use: {status.active_keys}</li>
            <li>Server key set in settings: {status.env_key_configured ? "yes" : "no"}</li>
            <li>First key can still be created: {status.bootstrap_available ? "yes" : "no"}</li>
          </ul>
        ) : !error ? (
          <div className="mt-3" role="status" data-testid="settings-status-loading">
            <span className="sr-only">Loading API status.</span>
            <div className="space-y-2" aria-hidden>
              <Skeleton className="h-4 w-56" />
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-60" />
              <Skeleton className="h-4 w-44" />
            </div>
          </div>
        ) : null}
        {status?.bootstrap_available ? (
          <div className="stg-actions">
            <Button
              type="button"
              variant="primary"
              disabled={busy}
              loading={busy}
              onClick={onBootstrap}
              data-testid="settings-bootstrap-btn"
            >
              {BOOTSTRAP_CTA}
            </Button>
          </div>
        ) : null}
      </section>

      <section className="stg-panel" data-testid="settings-browser-panel">
        <form onSubmit={onSaveLocal}>
          <h2 className="stg-panel-title">Browser key</h2>
          <p className="stg-panel-sub">
            Stored in localStorage on this device and sent as Authorization Bearer. Not synced to
            Ingenium servers.
          </p>
          <Input
            value={localKey}
            onChange={(e) => setLocalKey(e.target.value)}
            placeholder="oc_…"
            autoComplete="off"
            className="font-mono text-sm"
            aria-label="Browser API key"
          />
          <div className="stg-actions">
            <Button type="submit" variant="secondary" data-testid="settings-save-browser-btn">
              {SAVE_CTA}
            </Button>
          </div>
        </form>
      </section>

      <section className="stg-panel" data-testid="settings-sound-panel">
        <h2 className="stg-panel-title">Sound and reading</h2>
        <SoundToggle />
        <ReadingComfortToggle />
        <DisplayNameField />
        <ThemePicker />
        <DensityPicker />
        <OdooDimToggle />
      </section>

      <section className="stg-panel" data-testid="settings-trust-panel">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="stg-panel-title" style={{ marginBottom: 0 }}>
            Trust and safety
          </h2>
          <Link href="/settings/trust-safety" className="stg-link">
            Open safety contract
          </Link>
        </div>
        <p className="stg-panel-sub" style={{ marginTop: 8, marginBottom: 0 }}>
          Permission model, reversibility table, blast-radius limits, and incident playbook.
        </p>
      </section>

      {showCreate ? (
        <section className="stg-panel" data-testid="settings-create-panel">
          <form onSubmit={onCreateKey}>
            <h2 className="stg-panel-title">Create key</h2>
            <p className="stg-panel-sub">
              The full secret appears once after create. Give each key a name you can revoke later.
            </p>
            <Input
              id="settings-new-key-name"
              aria-label="Key name"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Key name"
            />
            <div className="stg-actions">
              <Button
                type="submit"
                variant="primary"
                disabled={busy}
                loading={busy}
                data-testid="settings-create-key-btn"
              >
                {PRIMARY_CTA}
              </Button>
            </div>
          </form>
        </section>
      ) : null}

      {revealed ? (
        <section className="stg-panel" data-testid="settings-reveal-panel">
          <h2 className="stg-panel-title">New key (shown once)</h2>
          <p className="stg-panel-sub">
            Copy now. Ingenium keeps only a hash. This value cannot be retrieved later.
          </p>
          <div className="stg-reveal">
            <pre className="font-mono text-xs">{revealed}</pre>
            <div className="stg-actions">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => void onCopyRevealed()}
                data-testid="settings-copy-key-btn"
              >
                {copied ? "Copied" : "Copy key"}
              </Button>
            </div>
          </div>
        </section>
      ) : null}

      {keys.length > 0 ? (
        <section className="stg-panel" data-testid="settings-keys-panel">
          <h2 className="stg-panel-title">Keys</h2>
          <p className="stg-panel-sub">Active and revoked keys for this workspace.</p>
          <ul className="mt-1 list-none space-y-0 p-0">
            {keys.map((k) => (
              <li key={k.id}>
                <div className="stg-key-row">
                  <span>
                    {k.name}{" "}
                    <span className="font-mono text-muted">
                      {k.key_prefix}…
                    </span>
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
                      data-testid={`settings-revoke-${k.id}`}
                      onClick={() => setRevokeTarget(k)}
                    >
                      Revoke
                    </Button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : keysListed ? (
        <section className="stg-panel" data-testid="settings-keys-empty">
          <h2 className="stg-panel-title">Keys</h2>
          <div className="mt-3">
            <EmptyState
              title="No API keys yet"
              description="Keys you create appear here with their prefix and a Revoke button."
              action={
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => document.getElementById("settings-new-key-name")?.focus()}
                >
                  Name a key
                </Button>
              }
            />
          </div>
        </section>
      ) : null}

      {status?.auth_mode === "accounts" && oauthIdentities.length > 0 ? (
        <section className="stg-panel" data-testid="settings-oauth-panel">
          <h2 className="stg-panel-title">Linked sign-in providers</h2>
          <p className="stg-panel-sub">Providers linked to this account.</p>
          <ul className="mt-1 list-none space-y-0 p-0">
            {oauthIdentities.map((row) => (
              <li key={row.provider}>
                <div className="stg-key-row">
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
                    onClick={() => void onUnlinkOAuth(row.provider)}
                  >
                    Unlink
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="stg-panel" data-testid="settings-audit-panel">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="stg-panel-title" style={{ marginBottom: 0 }}>
            Audit log
          </h2>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() =>
              refresh().catch((err: Error) => {
                setErrorContext("load");
                setError(err.message);
              })
            }
          >
            Refresh
          </Button>
        </div>
        <p className="stg-panel-sub" style={{ marginTop: 8 }}>
          Recent mutating API requests (POST, PUT, PATCH, DELETE).
        </p>
        <div className="mt-2">
          {!auditHydrated ? (
            <div role="status" data-testid="settings-audit-loading">
              <span className="sr-only">Loading the audit log.</span>
              <div className="space-y-2" aria-hidden>
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            </div>
          ) : auditLogs.length === 0 ? (
            AUDIT_EMPTY
          ) : (
            <DataTable
              columns={auditColumns}
              rows={auditLogs}
              rowKey={(r) => r.id}
              emptyState={AUDIT_EMPTY}
            />
          )}
        </div>
      </section>

      <p className="stg-lead" data-testid="settings-billing-note">
        Plan and invoices live under{" "}
        <Link href="/settings/billing" className="stg-link">
          Billing
        </Link>
        . This hub stays on API keys and audit.
      </p>

      <ConfirmDialogV2
        open={revokeTarget != null}
        riskLevel="danger"
        title="Revoke API key"
        warning={
          revokeTarget
            ? `Revoke ${revokeTarget.name} (${revokeTarget.key_prefix}…). Clients using this key will lose API access immediately.`
            : ""
        }
        risks={[
          "The key stops working for every client that holds it",
          "Revoke cannot be undone; create a new key if you still need access",
          "Audit history for past requests is kept",
        ]}
        phrase={REVOKE_PHRASE}
        busy={busy}
        onCancel={() => setRevokeTarget(null)}
        onConfirm={() => {
          void onRevokeConfirm();
        }}
      />
    </div>
  );
}
