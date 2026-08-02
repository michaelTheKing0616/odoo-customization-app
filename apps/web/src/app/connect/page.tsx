"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { CapabilityProbePanel } from "@/components/CapabilityProbePanel";
import { api, Connection } from "@/lib/api";

type EditForm = {
  name: string;
  url: string;
  db_name: string;
  username: string;
  password: string;
};

export default function ConnectPage() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
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
    try {
      const created = await api.createConnection({ ...form, verify: true });
      setForm((f) => ({ ...f, password: "" }));
      setLastSavedCaps(created.capabilities ?? null);
      setNotice(
        created.capabilities?.message
          ? `Connection saved. ${created.capabilities.message}`
          : created.server_version
            ? `Connection saved. Detected ${created.server_version}.`
            : "Connection saved.",
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save connection");
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
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    if (!deleteTargetId) return;
    setBusy(true);
    setError(null);
    try {
      // Delete connection does not require phrase on API; ConfirmDialog still gates UX.
      await api.deleteConnection(deleteTargetId);
      setDeleteTargetId(null);
      setNotice("Connection removed from app metadata.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
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
          (result.server_version
            ? `Probe ok — ${result.server_version}`
            : "Probe ok."),
      );
      // Refresh list so server_version + derived capabilities are not stale.
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Probe failed");
    } finally {
      setProbingId(null);
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(ellipse_at_top,_#3d2a38_0%,_#1a1218_50%,_#0c090b_100%)] px-6 py-12 text-[#f4eef2]">
      <div className="mx-auto max-w-3xl">
        <Link href="/" className="text-sm text-[#c9a9c0] hover:underline">
          ← Odoo Custom
        </Link>
        <Link href="/settings" className="ml-4 text-sm text-[#8f7a88] hover:underline">
          API settings
        </Link>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-4xl text-[#faf6f9]">
          Connect your Odoo
        </h1>
        <p className="mt-2 max-w-xl text-[#d4c4ce]">
          URL, database, and API key (or password). Credentials are encrypted at
          rest. Verified against Odoo 19 before save.
        </p>

        <form
          onSubmit={onSubmit}
          className="mt-10 space-y-4 border border-[#3d2a38] bg-[#0f1a16]/80 p-6"
        >
          {(
            [
              ["name", "Label", "text"],
              ["url", "Odoo URL", "url"],
              ["db_name", "Database", "text"],
              ["username", "Username", "text"],
              ["password", "Password / API key", "password"],
            ] as const
          ).map(([key, label, type]) => (
            <label key={key} className="block text-sm">
              <span className="text-[#a8909e]">{label}</span>
              <input
                type={type}
                required
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-[#f4eef2] outline-none focus:border-[#c9a9c0]"
              />
            </label>
          ))}
          {error && <p className="text-sm text-[#f0a8a0]">{error}</p>}
          {notice && <p className="text-sm text-[#c9a9c0]">{notice}</p>}
          {lastSavedCaps && (
            <CapabilityProbePanel
              capabilities={lastSavedCaps}
              defaultOpen
              className="pt-1"
            />
          )}
          <button
            type="submit"
            disabled={saving}
            className="h-11 bg-[#714B67] px-5 text-sm font-semibold text-white disabled:opacity-60"
          >
            {saving ? "Verifying…" : "Save connection"}
          </button>
        </form>

        <section className="mt-12">
          <h2 className="font-[family-name:var(--font-display)] text-2xl">
            Saved connections
          </h2>
          <ul className="mt-4 space-y-3">
            {connections.length === 0 && (
              <li className="text-sm text-[#8f7a88]">None yet.</li>
            )}
            {connections.map((c) => (
              <li
                key={c.id}
                className="border border-[#3d2a38] px-4 py-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-medium text-[#faf6f9]">{c.name}</p>
                    <p className="text-sm text-[#8f7a88]">
                      {c.url} · {c.db_name} · {c.server_version ?? "version unknown"}
                    </p>
                    <CapabilityProbePanel
                      capabilities={c.capabilities}
                      className="mt-2"
                      onRefresh={() => void reprobe(c.id)}
                      refreshing={probingId === c.id}
                    />
                  </div>
                  <div className="flex flex-wrap gap-2 text-sm">
                    <Link
                      href={`/connections/${c.id}/builder`}
                      className="bg-[#714B67] px-3 py-1.5 font-semibold text-white"
                    >
                      Build
                    </Link>
                    <Link
                      href={`/connections/${c.id}/designer`}
                      className="border border-[#c9a9c0] px-3 py-1.5 text-[#c9a9c0]"
                    >
                      Views
                    </Link>
                    <Link
                      href={`/connections/${c.id}/automations`}
                      className="border border-[#c9a9c0] px-3 py-1.5 text-[#c9a9c0]"
                    >
                      Automations
                    </Link>
                    <Link
                      href={`/connections/${c.id}/access`}
                      className="border border-[#c9a9c0] px-3 py-1.5 text-[#c9a9c0]"
                    >
                      Access
                    </Link>
                    <Link
                      href={`/connections/${c.id}`}
                      className="border border-[#3d2a38] px-3 py-1.5 text-[#d4c4ce]"
                    >
                      Browse
                    </Link>
                    <button
                      type="button"
                      onClick={() => startEdit(c)}
                      className="border border-[#3d2a38] px-3 py-1.5 text-[#d4c4ce]"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeleteTargetId(c.id)}
                      className="border border-[#5a3a36] px-3 py-1.5 text-[#f0a8a0]"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                {editingId === c.id && (
                  <form
                    onSubmit={onUpdate}
                    className="mt-4 space-y-3 border-t border-[#3d2a38] pt-4"
                  >
                    <p className="text-sm text-[#a8909e]">
                      Update connection (password optional — leave blank to keep current)
                    </p>
                    {(
                      [
                        ["name", "Label", "text"],
                        ["url", "Odoo URL", "url"],
                        ["db_name", "Database", "text"],
                        ["username", "Username", "text"],
                        ["password", "New password / API key", "password"],
                      ] as const
                    ).map(([key, label, type]) => (
                      <label key={key} className="block text-sm">
                        <span className="text-[#a8909e]">{label}</span>
                        <input
                          type={type}
                          required={key !== "password"}
                          value={editForm[key]}
                          onChange={(e) =>
                            setEditForm({ ...editForm, [key]: e.target.value })
                          }
                          className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 text-[#f4eef2] outline-none focus:border-[#c9a9c0]"
                          autoComplete={key === "password" ? "new-password" : "off"}
                        />
                      </label>
                    ))}
                    <div className="flex gap-2">
                      <button
                        type="submit"
                        disabled={saving}
                        className="h-10 bg-[#714B67] px-4 text-sm font-semibold text-white disabled:opacity-60"
                      >
                        {saving ? "Saving…" : "Save changes"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingId(null)}
                        className="h-10 border border-[#3d2a38] px-4 text-sm text-[#d4c4ce]"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                )}
              </li>
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
