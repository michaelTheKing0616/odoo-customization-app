"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Tabs } from "@/components/ui/Tabs";
import { Badge } from "@/components/ui/Badge";
import { Card, Skeleton } from "@/components/ui/layout-primitives";
import type { ExplorerTab, SnapshotModelDetail } from "@/lib/api";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { FieldEditor } from "./edit/FieldEditor";
import type { Gate } from "./edit/gates";
import { LockedNote } from "./edit/LockedNote";
import { AccessAdder, AutomationAdder, CodeExtender, MenuAdder, ViewExtender } from "./edit/StockExtend";
import { useModelDetail } from "./use-live-snapshot";

const MAX_RESULTS = 40;

function none(text: string) {
  return <p className="text-muted">{text}</p>;
}

type EditTarget = { mode: "add" } | { mode: "edit"; field: SnapshotModelDetail["fields"][number] } | null;

/** Plan gates for every change the explorer offers (from can_change). */
export type ExplorerGates = { field: Gate; view: Gate; automation: Gate; access: Gate; menu: Gate; code: Gate };
type Panel = "view" | "automation" | "access" | "menu" | "code" | null;

function Detail({ d, tab, onTab, connectionId, gates, onApplied }: {
  d: SnapshotModelDetail; tab: ExplorerTab; onTab: (t: ExplorerTab) => void;
  connectionId: string; gates: ExplorerGates; onApplied: () => void;
}) {
  const fieldGate = gates.field;
  const rules = d.record_rules;
  const stock = !d.custom;
  const [editing, setEditing] = useState<EditTarget>(null);
  const [panel, setPanel] = useState<Panel>(null);
  useEffect(() => { setEditing(null); setPanel(null); }, [d.model]);
  const done = () => { setEditing(null); setPanel(null); onApplied(); };
  const panelProps = { connectionId, d, onDone: done, onCancel: () => setPanel(null) };
  // Built-in models only: each tab offers its own extension, or says plainly why it's locked.
  const extendBar = (p: Exclude<Panel, null>, label: string, g: Gate, testId: string) => !stock ? null : (
    <div className="mb-2">
      {g.allowed ? (
        <Button variant="secondary" size="sm" onClick={() => setPanel(p)} disabled={panel !== null} data-testid={testId}>{label}</Button>
      ) : <LockedNote what={label} gate={g} testId={`${testId}-locked`} />}
    </div>
  );
  const shown = (p: Exclude<Panel, null>, node: React.ReactNode) => (panel === p ? <div className="mb-3">{node}</div> : null);
  const fieldBar = (
    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
      <p className="text-ui-meta text-muted">
        {d.custom ? "Custom model: add fields or edit the ones you added."
          : "Odoo's own fields can't be changed in place. Add your own field, then show it on the form with Extend this view on the Views tab."}
      </p>
      {fieldGate.allowed ? (
        <Button variant="secondary" size="sm" onClick={() => setEditing({ mode: "add" })} data-testid="add-field"
          disabled={editing !== null}>Add field</Button>
      ) : <LockedNote what="Adding fields" gate={fieldGate} testId="add-field-locked" />}
    </div>
  );
  const items: { value: ExplorerTab; label: string; content: React.ReactNode }[] = [
    { value: "fields", label: `Fields (${d.fields.length})`, content: (
      <div data-testid="tab-fields">
        {fieldBar}
        {editing ? (
          <div className="mb-3">
            <FieldEditor
              key={editing.mode === "edit" ? editing.field.name : "add"}
              connectionId={connectionId}
              model={d.model}
              modelLabel={d.label || d.model}
              field={editing.mode === "edit" ? editing.field : undefined}
              onDone={done}
              onCancel={() => setEditing(null)}
            />
          </div>
        ) : null}
        {d.fields.length === 0 ? none("We couldn't read the fields of this model.") : (
          <div className="max-h-[26rem] overflow-auto rounded-md border border-border-subtle">
            <table className="w-full text-left text-ui-meta">
              <thead className="sticky top-0 z-10 bg-surface-muted text-ui-label text-muted">
                <tr><th className="px-3 py-2 font-medium">Field</th><th className="px-3 py-2 font-medium">Type</th><th className="px-3 py-2 font-medium">Details</th><th className="px-3 py-2"><span className="sr-only">Edit</span></th></tr>
              </thead>
              <tbody>
                {d.fields.map((f) => (
                  <tr key={f.name} className="border-t border-border-subtle hover:bg-surface-muted/60">
                    <td className="px-3 py-1.5"><span className="block text-ui-body text-ink">{f.string || f.name}</span><span className="font-mono text-ui-mono text-muted">{f.name}</span></td>
                    <td className="px-3 py-1.5"><span className="rounded bg-surface-muted px-1.5 py-0.5 font-mono text-ui-mono text-muted">{f.type}</span></td>
                    <td className="px-3 py-1.5 text-muted">
                      {[f.required ? "required" : "", f.relation ? `→ ${f.relation}` : "",
                        f.selection.length ? f.selection.slice(0, 4).join(", ") : ""].filter(Boolean).join(" · ")}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      {f.custom && f.id != null && fieldGate.allowed ? (
                        <button type="button" className="text-ui-meta font-medium text-accent hover:underline"
                          onClick={() => setEditing({ mode: "edit", field: f })} aria-label={`Edit ${f.string || f.name}`}>
                          Edit
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    ) },
    { value: "views", label: "Views", content: (
      <div data-testid="tab-views" className="space-y-2">
        {stock ? <p className="text-ui-meta text-muted" data-testid="stock-views-note">Odoo&apos;s original screens are never edited in place; changes go into an extension view on top.</p> : null}
        {extendBar("view", "Extend this view", gates.view, "extend-view-btn")}
        {shown("view", <ViewExtender {...panelProps} />)}
        <Link href={`/connections/${connectionId}/designer?model=${encodeURIComponent(d.model)}`}
          className="inline-block text-ui-body font-medium text-accent hover:underline" data-testid="open-designer">
          Open in Designer <span aria-hidden>→</span>
        </Link>
        {d.views.types.length === 0 ? none("No screens defined for this model.") : (
          <p className="text-ui-body text-ink">
            {d.views.types.join(", ")}
            {d.views.form_field_count ? <span className="text-muted"> · form shows {d.views.form_field_count} fields</span> : null}
          </p>
        )}
      </div>
    ) },
    { value: "rules", label: rules.source === "ir.access" ? "Access rules" : "Rules", content: (
      <div data-testid="tab-rules">
        {extendBar("access", "Add access rights", gates.access, "add-access-btn")}
        {shown("access", <AccessAdder {...panelProps} />)}
        {rules.rows.length === 0 && !(rules.access ?? []).length ? none(rules.source === "ir.access"
          ? "No access rules, so only the administrator can open this model."
          : "No access or record rules, so only the administrator can open this model.") : (
          <ul className="space-y-1 text-ui-body" data-testid="explorer-rules">
            {(rules.access ?? []).map((r, i) => (
              <li key={`acl${i}`}><span className="text-ink">{r.name}</span> <span className="text-muted">· {r.group} · {r.operation || "none"}</span></li>
            ))}
            {rules.rows.map((r, i) => (
              <li key={i}>
                <span className="text-ink">{r.name}</span>{" "}
                <span className="text-muted">· {r.group} · {r.operation || "none"}{r.kind === "restriction" ? " · restriction" : ""}</span>
                {r.domain ? <div className="text-ui-mono text-muted">{r.domain}</div> : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    ) },
    { value: "actions", label: "Actions", content: (
      <div data-testid="tab-actions">
        {extendBar("automation", "Add automation rule", gates.automation, "add-automation-btn")}
        {shown("automation", <AutomationAdder {...panelProps} />)}
        {d.server_actions.length === 0 ? none("No server actions on this model.") : (
          <ul className="space-y-0.5 text-ui-body">{d.server_actions.map((a, i) => <li key={i} className="text-ink">{a.name} <span className="text-muted">· {a.kind}</span></li>)}</ul>
        )}
      </div>
    ) },
    { value: "menus", label: "Menus", content: (
      <div data-testid="tab-menus">
        {extendBar("menu", "Add menu", gates.menu, "add-menu-btn")}
        {shown("menu", <MenuAdder {...panelProps} />)}
        {d.menus.length === 0 ? none("No menu opens this model.") : (
          <ul className="space-y-0.5 text-ui-body">{d.menus.map((m) => <li key={m} className="text-ink">{m}</li>)}</ul>
        )}
      </div>
    ) },
  ];
  return (
    <div className="space-y-3" data-testid="explorer-detail">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-ui-title font-medium text-ink">{d.label || d.model}</h3>
        <span className="text-ui-mono text-muted">{d.model}</span>
        {d.custom ? <Badge variant="info">Custom</Badge> : null}
        {stock && gates.code.allowed ? (
          <Button variant="ghost" size="sm" className="ml-auto" onClick={() => setPanel("code")} disabled={panel !== null}
            data-testid="extend-code-btn">Extend with custom code</Button>
        ) : null}
      </div>
      {stock && !gates.code.allowed ? <LockedNote what="Extending with custom code" gate={gates.code} testId="extend-code-locked" /> : null}
      {shown("code", <CodeExtender {...panelProps} />)}
      <Tabs value={tab} onValueChange={(v) => onTab(v as ExplorerTab)} items={items} />
    </div>
  );
}

/** Touch 96: the hint names a model this database really has (a custom one first), so trying it always finds something. */
export function tryPlaceholder(models: { model: string; label: string }[]): string {
  const pick = models.find((m) => m.model.startsWith("x_") && m.label.trim()) ?? models.find((m) => m.label.trim() && !m.model.startsWith("ir."));
  return pick ? `Try: ${pick.label.trim()}` : "Search models";
}

export function ModelExplorer({ connectionId, models, model, tab, onSelect, onTab, gates, onApplied }: {
  connectionId: string;
  gates: ExplorerGates;
  /** Called after an Apply so the page can re-read the snapshot. */
  onApplied: () => void;
  models: { model: string; label: string }[];
  /** Controlled from the URL (?model=&tab=). */
  model: string | null;
  tab: ExplorerTab;
  onSelect: (model: string) => void;
  onTab: (tab: ExplorerTab) => void;
}) {
  const [query, setQuery] = useState("");
  const { selected, detail, open, close, refresh } = useModelDetail(connectionId);
  const listRef = useRef<HTMLUListElement>(null);
  useEffect(() => {
    if (model) open(model);
    else close();
  }, [model, open, close]);
  const options = () => Array.from(listRef.current?.querySelectorAll<HTMLButtonElement>('[role="option"]') ?? []);
  const move = (from: HTMLElement | null, delta: number) => {
    const opts = options();
    if (!opts.length) return;
    const i = from ? opts.indexOf(from as HTMLButtonElement) : -1;
    opts[Math.max(0, Math.min(opts.length - 1, i + delta))]?.focus();
  };
  const onListKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      move(document.activeElement as HTMLElement, e.key === "ArrowDown" ? 1 : -1);
    } else if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      const opts = options();
      opts[e.key === "Home" ? 0 : opts.length - 1]?.focus();
    }
  };
  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const hits = q ? models.filter((m) => m.model.includes(q) || m.label.toLowerCase().includes(q)) : models;
    // Custom models first (Supabase pattern: your tables before system tables).
    const ordered = [...hits.filter((m) => m.model.startsWith("x_")), ...hits.filter((m) => !m.model.startsWith("x_"))];
    return ordered.slice(0, MAX_RESULTS);
  }, [models, query]);

  const custom = results.filter((m) => m.model.startsWith("x_"));
  const standard = results.filter((m) => !m.model.startsWith("x_"));
  const row = (m: { model: string; label: string }) => (
    <li key={m.model}>
      <button
        type="button"
        role="option"
        aria-selected={selected === m.model}
        onClick={() => onSelect(m.model)}
        className={`w-full border-l-2 px-3 py-1.5 text-left focus-visible:bg-surface-muted focus-visible:outline-none ${selected === m.model
          ? "border-accent bg-accent-subtle" : "border-transparent hover:bg-surface-muted"}`}
      >
        <span className="block truncate text-ui-body text-ink">{m.label || m.model}</span>
        <span className="block truncate font-mono text-ui-mono text-muted">{m.model}</span>
      </button>
    </li>
  );
  const group = (title: string) => (
    <li role="presentation" className="sticky top-0 z-10 bg-surface-raised px-3 pb-1 pt-3 text-ui-label font-medium uppercase tracking-wide text-subtle">{title}</li>
  );

  return (
    <Card className="scroll-mt-24 overflow-hidden p-0" data-testid="model-explorer" id="overview-explorer">
      <div className="border-b border-border-subtle px-4 py-3">
        <h3 className="text-ui-title font-semibold text-ink">Model explorer</h3>
        <p className="text-ui-meta text-muted">{`Search ${models.length} models. Opening one reads its structure only, never its records.`}</p>
      </div>
      <div className="grid md:grid-cols-[minmax(0,17rem)_minmax(0,1fr)]">
        <div className="border-b border-border-subtle md:border-b-0 md:border-r">
          <div className="p-3">
            <div className="relative">
            <input
              id="overview-explorer-search"
              type="search"
              aria-label="Search models"
              aria-keyshortcuts="/"
              onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); move(null, 1); } }}
              placeholder={tryPlaceholder(models)}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full rounded-md pr-9 border border-border-subtle bg-surface-raised px-3 py-1.5 text-ui-body text-ink focus:outline-none focus:ring-2 focus:ring-accent"
            />
              <kbd aria-hidden className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-border-subtle bg-surface-muted px-1.5 font-mono text-ui-mono text-muted">/</kbd>
            </div>
          </div>
          <ul ref={listRef} onKeyDown={onListKey} className="max-h-[30rem] overflow-auto pb-2" role="listbox" aria-label="Models">
            {results.length === 0 ? <li className="px-3 py-1 text-ui-body text-muted">No model matches “{query}”.</li> : null}
            {custom.length ? group("Custom") : null}
            {custom.map(row)}
            {standard.length && custom.length ? group("Standard") : null}
            {standard.map(row)}
          </ul>
        </div>
        <div className="min-w-0 p-4">
          {!selected ? (
            <div className="flex h-full min-h-40 items-center justify-center rounded-md border border-dashed border-border-subtle p-6 text-center">
              <p className="text-ui-body text-muted">Pick a model to see its fields, screens, rules and menus.</p>
            </div>
          ) : !detail || detail.status === "loading" ? (
            <div data-testid="explorer-loading" aria-busy><Skeleton className="h-6 w-48" /><Skeleton className="mt-3 h-40" /></div>
          ) : detail.status === "error" ? (
            <div role="alert" data-testid="explorer-error" className="rounded-md border border-border-subtle p-4">
              <p className="text-ui-body font-medium text-ink">{`Couldn't load ${selected}.`}</p>
              <p className="text-ui-meta text-muted">{detail.message}</p>
              <button type="button" className="mt-2 text-ui-body font-medium text-accent hover:underline" onClick={() => open(selected)}>Try again</button>
            </div>
          ) : (
            <Detail d={detail.data} tab={tab} onTab={onTab} connectionId={connectionId} gates={gates}
              onApplied={() => { refresh(detail.data.model); onApplied(); }} />
          )}
        </div>
      </div>
    </Card>
  );
}
