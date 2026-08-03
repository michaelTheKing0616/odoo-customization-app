"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { StatusPill } from "@/components/ui/StatusPill";
import { reportApiError } from "@/lib/api-error";
import { api, Connection } from "@/lib/api";

type EditForm = {
  name: string;
  url: string;
  db_name: string;
  username: string;
  password: string;
};

type Step = 1 | 2 | 3;

export default function ConnectPage() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [step, setStep] = useState<Step>(1);
  const [form, setForm] = useState({
    name: "Local Odoo 19",
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
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [probingId, setProbingId] = useState<string | null>(null);
  const [lastSavedCaps, setLastSavedCaps] = useState<Connection["capabilities"]>(null);
  const [lastSavedId, setLastSavedId] = useState<string | null>(null);

  async function refresh() {
    const rows = await api.listConnections();
    setConnections(rows);
  }

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    setStep(2);
    try {
      const created = await api.createConnection({ ...form, verify: true });
      setForm((f) => ({ ...f, password: "" }));
      setLastSavedCaps(created.capabilities ?? null);
      setLastSavedId(created.id);
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
      reportApiError(err, setError, { fallback: "Failed to save connection", toast: false });
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
          (result.server_version ? `Probe ok — ${result.server_version}` : "Probe ok."),
      );
      await refresh();
    } catch (err) {
      reportApiError(err, setError, { fallback: "Probe failed", toast: false });
    } finally {
      setProbingId(null);
    }
  }

  return (
    <main className="min-h-screen bg-surface px-6 py-12">
      <div className="mx-auto max-w-3xl">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Link href="/" className="text-accent hover:underline">
            ← Odoo Custom
          </Link>
          <Link href="/settings" className="text-muted hover:text-ink">
            API settings
          </Link>
        </div>

        <div className="mt-4">
          <PageHeader
            title="Connect your Odoo"
            description="URL, database, and API key (or password). Credentials are encrypted at rest and verified before save."
          />
        </div>

        <ol className="mb-8 flex flex-wrap gap-4 text-sm">
          {[
            [1, "Credentials"],
            [2, "Probe"],
            [3, "Summary"],
          ].map(([n, label]) => (
            <li
              key={n}
              className={
                step === n
                  ? "font-medium text-accent"
                  : step > (n as number)
                    ? "text-ink"
                    : "text-muted"
              }
            >
              {n}. {label}
            </li>
          ))}
        </ol>

        {step === 3 && lastSavedId ? (
          <Card className="mb-8 space-y-4 p-6">
            <Callout variant="info" title="You're connected">
              Your instance was probed successfully. Open Overview to browse models or jump
              straight into Build.
            </Callout>
            {lastSavedCaps ? (
              <CapabilityProbePanel capabilities={lastSavedCaps} defaultOpen />
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" asChild>
                <Link href={`/connections/${lastSavedId}`}>Go to Overview</Link>
              </Button>
              <Button variant="secondary" asChild>
                <Link href={`/connections/${lastSavedId}/builder`}>Build models</Link>
              </Button>
              <Button variant="ghost" type="button" onClick={() => setStep(1)}>
                Add another connection
              </Button>
            </div>
          </Card>
        ) : null}

        <Card className="p-6">
          <form onSubmit={onSubmit} className="space-y-4">
            <Input
              label="Label"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <Input
              label="Odoo URL"
              type="url"
              required
              hint="Example: http://127.0.0.1:8069"
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
            />
            <Input
              label="Database"
              required
              value={form.db_name}
              onChange={(e) => setForm({ ...form, db_name: e.target.value })}
            />
            <Input
              label="Username"
              required
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
            />
            <Input
              label="Password / API key"
              type="password"
              required
              hint="Use an Odoo API key when available — Settings → Users → API keys."
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />

            {step === 2 && saving ? (
              <Callout variant="info" title="Probing your instance">
                Checking version, edition, hosting, and capability matrix…
              </Callout>
            ) : null}

            {error ? <ErrorNotice message={error} showDiagnose={false} /> : null}
            {notice ? (
              <Callout variant="info" title="Saved">
                {notice}
              </Callout>
            ) : null}
            {lastSavedCaps && step !== 3 ? (
              <CapabilityProbePanel capabilities={lastSavedCaps} defaultOpen className="pt-1" />
            ) : null}

            <Button type="submit" variant="primary" loading={saving} disabled={saving}>
              {saving ? "Verifying…" : "Save connection"}
            </Button>
          </form>
        </Card>

        <section className="mt-12">
          <h2 className="text-xl font-semibold text-ink">Saved connections</h2>
          <ul className="mt-4 space-y-3">
            {connections.length === 0 && (
              <li className="text-sm text-muted">None yet.</li>
            )}
            {connections.map((c) => (
              <Card key={c.id} className="p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-ink">{c.name}</p>
                      {c.capabilities?.ga ? <StatusPill kind="ga" /> : null}
                      {!c.capabilities?.ga ? <StatusPill kind="experimental" /> : null}
                    </div>
                    <p className="text-sm text-muted">
                      {c.url} · {c.db_name} · {c.server_version ?? "version unknown"}
                    </p>
                    <CapabilityProbePanel
                      capabilities={c.capabilities}
                      className="mt-2"
                      onRefresh={() => void reprobe(c.id)}
                      refreshing={probingId === c.id}
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="primary" size="sm" asChild>
                      <Link href={`/connections/${c.id}`}>Overview</Link>
                    </Button>
                    <Button variant="secondary" size="sm" asChild>
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
                </div>

                {editingId === c.id ? (
                  <form onSubmit={onUpdate} className="mt-4 space-y-3 border-t border-border-subtle pt-4">
                    <p className="text-sm text-muted">
                      Update connection (password optional — leave blank to keep current)
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
                      label="New password / API key"
                      type="password"
                      value={editForm.password}
                      onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
                      autoComplete="new-password"
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
              </Card>
            ))}
          </ul>
        </section>
      </div>

      <ConfirmDialog
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
    </main>
  );
}
