"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { errorText } from "./PreviewApply";

type Row = { name: string; label: string };
type State = { kind: "idle" } | { kind: "loading" } | { kind: "list"; rows: Row[] } | { kind: "error"; message: string };

/** Install an available stock Odoo app (existing install-community path), with confirmation. */
export function AppInstaller({ connectionId, onInstalled }: { connectionId: string; onInstalled: () => void }) {
  const [state, setState] = useState<State>({ kind: "idle" });
  const [confirm, setConfirm] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setState({ kind: "loading" });
    try {
      const rows = await api.listModules(connectionId, { applicationsOnly: true, installedOnly: false });
      setState({
        kind: "list",
        rows: rows.filter((m) => m.state === "uninstalled").map((m) => ({ name: m.name, label: m.shortdesc || m.name }))
          .sort((a, b) => a.label.localeCompare(b.label)),
      });
    } catch (err) {
      setState({ kind: "error", message: errorText(err) });
    }
  }
  async function install(row: Row) {
    setBusy(true);
    setError(null);
    try {
      await api.installCommunityModule(connectionId, row.name);
      setConfirm(null);
      setState({ kind: "idle" });
      onInstalled();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  if (state.kind === "idle") {
    return <Button variant="secondary" size="sm" onClick={() => void load()} data-testid="add-app">Add an app</Button>;
  }
  if (state.kind === "loading") return <p className="text-ui-meta text-muted">Looking for apps you can add…</p>;
  if (state.kind === "error") {
    return (
      <p role="alert" className="text-ui-meta text-muted">
        {`We couldn't list the apps: ${state.message} `}
        <button type="button" className="font-medium text-accent hover:underline" onClick={() => void load()}>Try again</button>
      </p>
    );
  }
  if (confirm) {
    return (
      <div className="space-y-2 rounded-md border border-border-subtle bg-surface-muted p-3" data-testid="install-confirm">
        <p className="text-ui-body text-ink">{`Install ${confirm.label}?`}</p>
        <p className="text-ui-meta text-muted">Odoo adds the app and anything it depends on. This can take a minute and is shown to everyone on this database.</p>
        {error ? <p role="alert" className="text-ui-meta text-status-critical-strong">{`That didn't work: ${error}`}</p> : null}
        <div className="flex gap-2">
          <Button variant="primary" size="sm" disabled={busy} onClick={() => void install(confirm)} data-testid="install-confirm-yes">
            {busy ? "Installing…" : `Install ${confirm.label}`}
          </Button>
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => setConfirm(null)}>Cancel</Button>
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-1.5" data-testid="app-list">
      {state.rows.length === 0 ? <p className="text-ui-meta text-muted">Every available app is already installed.</p> : null}
      <ul className="max-h-48 space-y-0.5 overflow-auto">
        {state.rows.map((r) => (
          <li key={r.name} className="flex items-center justify-between gap-2 text-ui-body">
            <span className="truncate text-ink">{r.label}</span>
            <button type="button" className="shrink-0 font-medium text-accent hover:underline" onClick={() => setConfirm(r)}>
              Install
            </button>
          </li>
        ))}
      </ul>
      <button type="button" className="text-ui-meta text-muted hover:text-ink" onClick={() => setState({ kind: "idle" })}>Close</button>
    </div>
  );
}
