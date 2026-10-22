"use client";

import { useRouter } from "next/navigation";
import { canMorph, morphNavigate } from "@/lib/morph";
import { testCopyStatus } from "@/components/ui/craft";
import { forgetConfirmTarget } from "@/components/ui/useConfirmTarget";
import Link from "next/link";
import React, { FormEvent, useDeferredValue, useEffect, useMemo, useState } from "react";

const SAVED_PAGE = 50;
import { BrandMark } from "@/components/brand/BrandMark";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/layout-primitives";
import { StatusPill } from "@/components/ui/StatusPill";
import { reportApiError } from "@/lib/api-error";
import { api, Connection } from "@/lib/api";
import { ConnectApiKeyGuide } from "@/components/connect/ConnectApiKeyGuide";
import { ConnectChecklist } from "@/components/connect/ConnectChecklist";
import { ConnectStateGuide } from "@/components/connect/ConnectStateGuide";
import { ConnectStepRail } from "@/components/connect/ConnectStepRail";
import {
  credentialFieldCopy,
  DEFAULT_CONNECTION_LABEL,
  nextConnectionLabel,
} from "@/lib/connect-checklist";
import {
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  PRIMARY_CTA_BUSY,
  PROBE_STAGES,
  classifyConnectError,
  connectErrorGuide,
  connectObserverNote,
  connectSecretTip,
  connectedGuide,
  emptyConnectGuide,
  probeStageLabel,
  resolveConnectStep,
} from "@/lib/connectScreen";
import {
  detectHostingKind,
  hostingHint,
  HOSTING_CHOICES,
  type HostingKind,
  normalizeOdooBaseUrl,
  suggestDbFromUrl,
} from "@/lib/odoo-hosting";
import "@/components/connect/connect-operate.css";

type EditForm = {
  name: string;
  url: string;
  db_name: string;
  username: string;
  password: string;
};

type Step = 1 | 2 | 3;

export default function ConnectPage() {
  const router = useRouter();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [listHydrated, setListHydrated] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [probeElapsed, setProbeElapsed] = useState(0);
  const [step, setStep] = useState<Step>(1);
  const [form, setForm] = useState({
    name: DEFAULT_CONNECTION_LABEL,
    url: "http://127.0.0.1:8069",
    db_name: "odoo_dev",
    username: "admin",
    password: "admin",
  });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<EditForm>({
    name: "",
    url: "",
    db_name: "",
    username: "",
    password: "",
  });
  const [savedQuery, setSavedQuery] = useState("");
  // Saved list stays light however many connections exist (one account had 16,000; rendering all froze the page).
  const [savedLimit, setSavedLimit] = useState(SAVED_PAGE);
  const deferredQuery = useDeferredValue(savedQuery);
  const matchingSaved = useMemo(() => {
    const q = deferredQuery.trim().toLowerCase();
    return connections
      .filter((c) => !q || `${c.name} ${c.url} ${c.db_name} ${c.group_label ?? ""}`.toLowerCase().includes(q))
      .sort((a, b) => (a.group_label ?? "~").localeCompare(b.group_label ?? "~"));
  }, [connections, deferredQuery]);
  const shownSaved = useMemo(() => matchingSaved.slice(0, savedLimit), [matchingSaved, savedLimit]);
  useEffect(() => setSavedLimit(SAVED_PAGE), [deferredQuery]);
  const [groupLabel, setGroupLabel] = useState("");
  const [testCopy, setTestCopy] = useState(false);
  const [checks, setChecks] = useState<
    Record<string, Array<{ key: string; label: string; ok: boolean | null; detail: string }> | "loading">
  >({});
  const runChecks = (id: string) => {
    setChecks((m) => ({ ...m, [id]: "loading" }));
    api
      .liveCheck(id)
      .then((r) => setChecks((m) => ({ ...m, [id]: r.rows })))
      .catch((err: Error) =>
        setChecks((m) => ({ ...m, [id]: [{ key: "err", label: "Check", ok: false, detail: err.message }] })),
      );
  };
  const startTestCopy = (c: Connection) => {
    setForm((f) => ({
      ...f,
      name: `${c.name} (test copy)`,
      url: c.url,
      db_name: `${c.db_name}_test`,
      username: c.username,
      password: "",
    }));
    setGroupLabel(c.group_label ?? "");
    setTestCopy(true);
    setHostingChoice((c.hosting as HostingKind | null) ?? null);
    setStep(1);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [probingId, setProbingId] = useState<string | null>(null);
  const [lastSavedCaps, setLastSavedCaps] = useState<Connection["capabilities"]>(null);
  const [lastSavedId, setLastSavedId] = useState<string | null>(null);
  const [lastSavedVersion, setLastSavedVersion] = useState<string | null>(null);
  const [hostingChoice, setHostingChoice] = useState<HostingKind | null>(null);
  const detectedHosting = detectHostingKind(form.url);
  const hosting: HostingKind =
    hostingChoice ?? detectedHosting;
  const hostingExample = HOSTING_CHOICES.find((h) => h.kind === hosting)?.example;
  const hostingTip = hostingHint(hosting);
  const suggestedDb = suggestDbFromUrl(form.url);
  const credentialCopy = credentialFieldCopy(hosting);
  const checklistInput = {
    url: form.url,
    dbName: form.db_name,
    username: form.username,
    password: form.password,
    verified: step === 3,
  };

  const currentStep = resolveConnectStep({ step, saving });
  const observerNote = useMemo(() => connectObserverNote(), []);
  const secretTip = useMemo(
    () => connectSecretTip(hosting === "online"),
    [hosting],
  );

  useEffect(() => {
    if (!saving) {
      setProbeElapsed(0);
      return;
    }
    const started = Date.now();
    const id = window.setInterval(() => {
      setProbeElapsed(Date.now() - started);
    }, 200);
    return () => window.clearInterval(id);
  }, [saving]);

  async function refresh() {
    setListHydrated(false);
    try {
      const rows = await api.listConnections();
      setConnections(rows);
    } finally {
      setListHydrated(true);
    }
  }

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, []);

  // "Add connection" (sidebar switcher, Cmd-K) lands on /connect#new: start at the form with the first field ready.
  useEffect(() => {
    if (window.location.hash !== "#new") return;
    const el = document.getElementById("connect-form");
    el?.scrollIntoView({ block: "start" });
    el?.querySelector<HTMLInputElement>("input")?.focus();
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    setStep(2);
    try {
      const payload = { ...form, url: normalizeOdooBaseUrl(form.url) || form.url };
      const created = await api.createConnection({
        ...payload,
        verify: true,
        ...(hosting !== "unknown" ? { hosting } : {}),
        ...(groupLabel.trim() ? { group_label: groupLabel.trim() } : {}),
        is_test_copy: testCopy,
      });
      setTestCopy(false);
      setForm((f) => ({ ...f, password: "" }));
      setLastSavedCaps(created.capabilities ?? null);
      setLastSavedId(created.id);
      setLastSavedVersion(created.server_version ?? null);
      setNotice(
        created.capabilities?.message
          ? `Connection saved. ${created.capabilities.message}`
          : created.server_version
            ? `Connection saved. Detected ${created.server_version}.`
            : "Connection saved.",
      );
      await refresh();
      setStep(3);
    } catch (err) {
      reportApiError(
        err,
        (msg) => setError(msg || "Failed to save connection"),
        { fallback: "Failed to save connection", toast: false },
      );
      setStep(1);
    } finally {
      setSaving(false);
    }
  }

  function startEdit(c: Connection) {
    setEditingId(c.id);
    setEditForm({
      name: c.name,
      url: c.url,
      db_name: c.db_name,
      username: c.username,
      password: "",
    });
    setError(null);
    setNotice(null);
  }

  async function onUpdate(e: FormEvent) {
    e.preventDefault();
    if (!editingId) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const body: {
        name?: string;
        url?: string;
        db_name?: string;
        username?: string;
        password?: string;
        verify?: boolean;
      } = {
        name: editForm.name,
        url: editForm.url,
        db_name: editForm.db_name,
        username: editForm.username,
        verify: true,
      };
      if (editForm.password.trim()) {
        body.password = editForm.password;
      }
      const updated = await api.updateConnection(editingId, body);
      setEditingId(null);
      setLastSavedCaps(updated.capabilities ?? null);
      setNotice(
        updated.capabilities?.message
          ? `Connection updated. ${updated.capabilities.message}`
          : updated.server_version
            ? `Connection updated. Detected ${updated.server_version}.`
            : "Connection updated.",
      );
      await refresh();
    } catch (err) {
      reportApiError(err, setError, { fallback: "Update failed", toast: false });
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    if (!deleteTargetId) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteConnection(deleteTargetId);
      setDeleteTargetId(null);
      setNotice("Connection removed from app metadata.");
      await refresh();
    } catch (err) {
      reportApiError(err, setError, { fallback: "Delete failed", toast: false });
    } finally {
      setBusy(false);
    }
  }

  async function reprobe(id: string) {
    setProbingId(id);
    setError(null);
    try {
      const result = await api.probeConnection(id);
      setLastSavedCaps(result.capabilities ?? null);
      setNotice(
        result.capabilities?.message ??
          (result.server_version ? `Probe ok - ${result.server_version}` : "Probe ok."),
      );
      await refresh();
    } catch (err) {
      reportApiError(err, setError, { fallback: "Probe failed", toast: false });
    } finally {
      setProbingId(null);
    }
  }

  const errorGuide = error
    ? connectErrorGuide(classifyConnectError(error), error)
    : null;
  const activeProbeLabel = probeStageLabel(probeElapsed);
  const probeStageIndex = Math.min(
    PROBE_STAGES.length - 1,
    Math.floor(Math.max(0, probeElapsed) / 900),
  );

  return (
    <div className="connect-operate-desk">
      <div className="connect-operate" data-testid="connect-page">
        <header className="cn-topbar">
          <BrandMark size={28} priority />
          <nav className="cn-topbar-links" aria-label="Connect navigation">
            <Link href="/login">Sign in</Link>
            <Link href="/signup">Create account</Link>
            <Link href="/settings">API settings</Link>
          </nav>
        </header>

        <div className="cn-hero">
          <h1>{PAGE_TITLE}</h1>
          <p>{PAGE_DESCRIPTION}</p>
        </div>

        <ConnectStepRail current={currentStep} />

        {step === 3 && lastSavedId ? (
          <section className="cn-paper" data-testid="connect-first-win">
            <ConnectStateGuide
              testId="connect-connected-guide"
              tone="success"
              guide={connectedGuide({
                serverVersion: lastSavedVersion,
                capsMessage: lastSavedCaps?.message ?? null,
              })}
            />
            {lastSavedCaps ? (
              <CapabilityProbePanel capabilities={lastSavedCaps} defaultOpen className="mt-4" />
            ) : null}
            <ol className="cn-success-list">
              <li>
                <span>1</span>
                <span>
                  <strong>App Studio</strong> - describe what you need (no live write yet).
                </span>
              </li>
              <li>
                <span>2</span>
                <span>
                  <strong>Projects</strong> - keep the draft on the board.
                </span>
              </li>
              <li>
                <span>3</span>
                <span>
                  <strong>Overview</strong> - browse models when you want the full map.
                </span>
              </li>
            </ol>
            <div className="cn-success-actions">
              <Button variant="primary" asChild>
                <Link
                  href={`/connections/${lastSavedId}/studio`}
                  data-testid="connect-first-win-app-studio"
                >
                  Open App Studio
                </Link>
              </Button>
              <Button variant="secondary" asChild>
                <Link
                  href={`/connections/${lastSavedId}/projects`}
                  data-testid="connect-first-win-projects"
                >
                  Projects
                </Link>
              </Button>
              <Button variant="ghost" asChild>
                <Link href={`/connections/${lastSavedId}`} data-testid="connect-first-win-overview">
                  Overview
                </Link>
              </Button>
              <Button
                variant="ghost"
                type="button"
                onClick={() => {
                  setStep(1);
                  setNotice(null);
                }}
              >
                Add another
              </Button>
            </div>
          </section>
        ) : (
          <section className="cn-paper">
            {step !== 3 ? (
              <div className="cn-observer" data-testid="connect-honesty">
                <span className="cn-observer-mark" aria-hidden />
                <p data-testid="connect-honesty-title">{observerNote}</p>
              </div>
            ) : null}

            <form id="connect-form" onSubmit={onSubmit} className="space-y-4">
              <ConnectChecklist input={checklistInput} showCapabilities={false} />

              <div className="cn-field-grid cn-cols-2">
                <Input
                  label="Label"
                  required
                  hint="Tracks the database name until you edit it."
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
                <Input
                  label="Database"
                  required
                  value={form.db_name}
                  onChange={(e) => {
                    const nextDb = e.target.value;
                    setForm((f) => ({
                      ...f,
                      db_name: nextDb,
                      name: nextConnectionLabel(f.name, f.db_name, nextDb),
                    }));
                  }}
                />
              </div>

              <fieldset className="cn-hosting" data-testid="connect-hosting-picker">
                <legend>Where is your Odoo?</legend>
                {form.url.trim() && detectedHosting !== "unknown" ? (
                  <p className="cn-hosting-note" data-testid="connect-hosting-detected">
                    Looks like {HOSTING_CHOICES.find((h) => h.kind === hosting)?.label}. Change it if that&apos;s wrong.
                  </p>
                ) : null}
                <div className="cn-hosting-options" role="radiogroup">
                  {HOSTING_CHOICES.map((h) => (
                    <button
                      key={h.kind}
                      type="button"
                      role="radio"
                      aria-checked={hosting === h.kind}
                      data-active={hosting === h.kind ? "true" : "false"}
                      onClick={() => setHostingChoice(h.kind)}
                      data-testid={`connect-hosting-${h.kind}`}
                    >
                      {h.label}
                    </button>
                  ))}
                </div>
              </fieldset>

              <Input
                label="Group (optional)"
                hint="For agencies: the client or team this database belongs to"
                value={groupLabel}
                maxLength={80}
                onChange={(e) => setGroupLabel(e.target.value)}
                data-testid="connect-group-label"
              />

              <Input
                label="Odoo URL"
                placeholder={hostingExample}
                type="url"
                required
                hint="Site root only - https://mycompany.odoo.com or http://127.0.0.1:8069 (no /odoo path)"
                value={form.url}
                onChange={(e) => {
                  const url = e.target.value;
                  setHostingChoice(null);
                  const dbGuess = suggestDbFromUrl(url);
                  setForm((f) => {
                    const nextDb =
                      dbGuess &&
                      (!f.db_name || f.db_name === "odoo_dev" || f.db_name === suggestedDb)
                        ? dbGuess
                        : f.db_name;
                    return {
                      ...f,
                      url,
                      db_name: nextDb,
                      name: nextConnectionLabel(f.name, f.db_name, nextDb),
                    };
                  });
                }}
                onBlur={() =>
                  setForm((f) => ({ ...f, url: normalizeOdooBaseUrl(f.url) || f.url }))
                }
              />

              {hostingTip ? (
                <Callout variant="info" title="Hosting tip" testId="connect-hosting-tip">
                  {hostingTip}
                </Callout>
              ) : null}

              <div className="cn-field-grid cn-cols-2">
                <Input
                  label="Username"
                  required
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                />
                <Input
                  label={credentialCopy.label}
                  type="password"
                  required
                  hint={credentialCopy.hint}
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  autoComplete="current-password"
                  data-testid="connect-secret"
                />
              </div>

              {secretTip ? (
                <p className="cn-secret-tip" data-testid="connect-api-key-honesty">
                  {secretTip}
                </p>
              ) : null}

              <ConnectApiKeyGuide
                url={form.url}
                hosting={hosting}
                errorMessage={error}
              />

              {saving ? (
                <div
                  className="cn-probe"
                  aria-busy="true"
                  role="status"
                  data-testid="connect-probe-progress"
                >
                  <p className="cn-probe-label">{activeProbeLabel}</p>
                  <div className="cn-probe-track" aria-hidden>
                    <div className="cn-probe-fill" />
                  </div>
                  <ol className="cn-probe-stages" aria-label="Probe stages">
                    {PROBE_STAGES.map((label, i) => {
                      const state =
                        i < probeStageIndex ? "done" : i === probeStageIndex ? "current" : "todo";
                      return (
                        <li key={label} data-state={state}>
                          {label.replace("…", "")}
                        </li>
                      );
                    })}
                  </ol>
                </div>
              ) : null}

              {errorGuide ? (
                <ConnectStateGuide
                  testId="connect-error-guide"
                  tone="danger"
                  live
                  guide={errorGuide}
                />
              ) : null}
              {error && !errorGuide ? <ErrorNotice message={error} showDiagnose={false} /> : null}
              {notice && step !== 3 ? (
                <Callout variant="info" title="Saved">
                  {notice}
                </Callout>
              ) : null}
              {lastSavedCaps && step !== 3 ? (
                <CapabilityProbePanel capabilities={lastSavedCaps} defaultOpen className="pt-1" />
              ) : null}

              <div className="cn-actions">
                <p className="cn-actions-hint">
                  Credentials are encrypted at rest. The secret field stays write-only after save.
                </p>
                <Button
                  type="submit"
                  variant="primary"
                  loading={saving}
                  disabled={saving}
                  data-testid="connect-add-btn"
                >
                  {saving ? PRIMARY_CTA_BUSY : PRIMARY_CTA}
                </Button>
              </div>
            </form>
          </section>
        )}

        <section className="cn-saved" data-testid="connect-saved-list">
          <div className="cn-saved-head">
            <h2>Saved connections</h2>
            {listHydrated ? (
              <p>
                {connections.length === 0
                  ? "None yet"
                  : `${connections.length} saved`}
              </p>
            ) : null}
          </div>

          {!listHydrated ? (
            <div className="cn-saved-paper p-4 space-y-3" data-testid="connect-saved-loading">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : connections.length === 0 ? (
            <div className="cn-saved-paper">
              <div className="cn-saved-empty" data-testid="connect-empty-guide">
                <svg width="72" height="46" viewBox="0 0 88 56" fill="none" aria-hidden="true" className="mb-2 text-muted">
                  <path d="M8 54V32a36 32 0 0 1 72 0v22M20 54V32a24 22 0 0 1 48 0v22" stroke="currentColor" strokeWidth="1.5" />
                </svg>
                <h3 data-testid="connect-empty-guide-title">{emptyConnectGuide().title}</h3>
                <p data-testid="connect-empty-guide-why">{emptyConnectGuide().why}</p>
                <p className="mt-3" data-testid="connect-empty-guide-next">
                  {emptyConnectGuide().next}
                </p>
              </div>
            </div>
          ) : (
            <>
            {connections.length > 3 ? (
              <Input
                type="search"
                className="mb-3"
                placeholder="Search by name, address or database"
                aria-label="Search saved connections"
                value={savedQuery}
                onChange={(e) => setSavedQuery(e.target.value)}
                data-testid="connect-saved-search"
              />
            ) : null}
            <ul className="cn-saved-paper">
              {shownSaved.map((c, i, arr) => (
                <React.Fragment key={c.id}>
                {c.group_label && c.group_label !== arr[i - 1]?.group_label ? (
                  <li className="cn-group-head" data-testid={`connect-group-${c.group_label}`}>
                    {c.group_label}
                  </li>
                ) : null}
                <li className="cn-row" data-testid={`connect-row-${c.id}`}>
                  <div className="cn-row-title">
                    <p>{c.name}</p>
                    {c.capabilities?.ga ? <StatusPill kind="ga" /> : null}
                    {!c.capabilities?.ga ? <StatusPill kind="experimental" /> : null}
                    <span
                      className="cn-health"
                      data-ok={c.capabilities && c.server_version ? "true" : "false"}
                      data-testid={`connect-health-${c.id}`}
                    >
                      {c.capabilities && c.server_version ? "Checked" : "Needs a check"}
                    </span>
                  </div>
                  <p className="cn-row-meta">
                    {c.url} · {c.db_name} · {c.server_version ?? "version unknown"}
                    {c.hosting ? ` · ${HOSTING_CHOICES.find((h) => h.kind === c.hosting)?.label ?? c.hosting}` : ""}
                  </p>
                  <CapabilityProbePanel
                    capabilities={c.capabilities}
                    className="mt-2"
                    onRefresh={() => void reprobe(c.id)}
                    refreshing={probingId === c.id}
                  />
                  {Array.isArray(checks[c.id]) ? (
                    <ul className="cn-checks" data-testid={`connect-checks-${c.id}`}>
                      {(checks[c.id] as Array<{ key: string; label: string; ok: boolean | null; detail: string }>).map((r) => (
                        <li key={r.key} data-ok={r.ok === null ? "unknown" : String(r.ok)}>
                          <span className="cn-check-label">{r.label}</span> {r.detail}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  <div className="cn-row-actions">
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={checks[c.id] === "loading"}
                      onClick={() => runChecks(c.id)}
                      data-testid={`connect-run-checks-${c.id}`}
                    >
                      Run checks
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => startTestCopy(c)} data-testid={`connect-test-copy-${c.id}`}>
                      Connect a test copy
                    </Button>
                    <label className="inline-flex items-center gap-1.5 text-xs text-muted" data-testid={`connect-is-test-copy-${c.id}`} title={c.is_test_copy == null ? "Not set yet. Ingenium guesses from the name until you tick or untick this." : undefined}>
                      <input
                        type="checkbox"
                        checked={testCopyStatus(c).test}
                        onChange={(e) => {
                          const v = e.target.checked;
                          setConnections((rows) => rows.map((r) => (r.id === c.id ? { ...r, is_test_copy: v } : r)));
                          api.updateConnection(c.id, { is_test_copy: v, verify: false }).then(
                            (row) => { forgetConfirmTarget(c.id); setConnections((rows) => rows.map((r) => (r.id === c.id ? { ...r, ...row } : r))); },
                            (err: Error) => { setConnections((rows) => rows.map((r) => (r.id === c.id ? c : r))); setNotice(`Couldn't save the test copy setting: ${err.message}`); },
                          );
                        }}
                      />
                      This is a test copy{c.is_test_copy == null ? " (guessed)" : ""}
                    </label>
                    <Button variant="primary" size="sm" asChild>
                      <Link href={`/connections/${c.id}/studio`}>App Studio</Link>
                    </Button>
                    <Button variant="secondary" size="sm" asChild>
                      <Link href={`/connections/${c.id}`} onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || !canMorph()) return; e.preventDefault(); morphNavigate((h) => router.push(h), `/connections/${c.id}`, (e.currentTarget as HTMLElement).closest("li")); }}>Overview</Link>
                    </Button>
                    <Button variant="ghost" size="sm" asChild>
                      <Link href={`/connections/${c.id}/builder`}>Build</Link>
                    </Button>
                    <Button variant="ghost" size="sm" type="button" onClick={() => startEdit(c)}>
                      Edit
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      type="button"
                      onClick={() => setDeleteTargetId(c.id)}
                    >
                      Delete
                    </Button>
                  </div>

                  {editingId === c.id ? (
                    <form
                      onSubmit={onUpdate}
                      className="mt-4 space-y-3 border-t border-border-subtle pt-4"
                    >
                      <p className="text-sm text-muted">
                        Password / API key optional - leave blank to keep current. Rotating the
                        Odoo RPC secret keeps this connection id and your drafts.
                      </p>
                      <Input
                        label="Label"
                        required
                        value={editForm.name}
                        onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                      />
                      <Input
                        label="Odoo URL"
                        type="url"
                        required
                        value={editForm.url}
                        onChange={(e) => setEditForm({ ...editForm, url: e.target.value })}
                      />
                      <Input
                        label="Database"
                        required
                        value={editForm.db_name}
                        onChange={(e) => setEditForm({ ...editForm, db_name: e.target.value })}
                      />
                      <Input
                        label="Username"
                        required
                        value={editForm.username}
                        onChange={(e) => setEditForm({ ...editForm, username: e.target.value })}
                      />
                      <Input
                        label="New Odoo password / RPC API key"
                        type="password"
                        value={editForm.password}
                        onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
                        autoComplete="new-password"
                        hint="Odoo's API secret only - not a Cursor MCP key."
                      />
                      <div className="flex gap-2">
                        <Button type="submit" variant="primary" size="sm" loading={saving}>
                          Save changes
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setEditingId(null)}
                        >
                          Cancel
                        </Button>
                      </div>
                    </form>
                  ) : null}
                </li>
                </React.Fragment>
              ))}
            </ul>
            {matchingSaved.length > shownSaved.length ? (
              <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted" data-testid="connect-saved-more">
                <span>
                  Showing {shownSaved.length.toLocaleString()} of {matchingSaved.length.toLocaleString()}. Search to find the rest.
                </span>
                <Button variant="secondary" size="sm" type="button" onClick={() => setSavedLimit((n) => n + SAVED_PAGE)}>
                  Show {Math.min(SAVED_PAGE, matchingSaved.length - shownSaved.length)} more
                </Button>
              </div>
            ) : null}
            </>
          )}
        </section>
      </div>

      <ConfirmDialogV2
        riskLevel="danger"
        open={deleteTargetId != null}
        title="Delete connection?"
        warning="This removes the connection and related app metadata. Odoo-side customizations (fields, views, automations) remain on the database."
        risks={[
          "App snapshots, sandbox validations, and promotion records for this connection are deleted",
          "Encrypted credentials stored in this app are removed",
          "Nothing is uninstalled or deleted inside Odoo itself",
        ]}
        onCancel={() => setDeleteTargetId(null)}
        onConfirm={() => {
          void confirmDelete();
        }}
        busy={busy}
      />
    </div>
  );
}
