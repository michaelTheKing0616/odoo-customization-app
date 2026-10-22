"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { useCallback, useEffect } from "react";
import { goToSection, useExplorerUrl } from "./use-explorer-url";
import type { AttentionItem, ExplorerTab, LiveSnapshot, OverviewSectionId } from "@/lib/api";
import Link from "next/link";
import { useState } from "react";
import { AttentionStrip } from "./AttentionStrip";
import { AppInstaller } from "./edit/AppInstaller";
import { AttentionFix, fixKindFor, type FixKind } from "./edit/AttentionFix";
import { gate, type Gate } from "./edit/gates";
import { LockedNote } from "./edit/LockedNote";
import { SummaryCards } from "./SummaryCards";
import { CHANGE_COPY, EDITION_COPY, HOSTING_COPY, availabilityLabel } from "./live-copy";
import { ModelExplorer, type ExplorerGates } from "./ModelExplorer";
import { useLiveSnapshot } from "./use-live-snapshot";
import { Term } from "@/components/ui/Term";

function SectionCard({ id, title, count, children, testId }: {
  id: OverviewSectionId; title: string; count?: number; children: React.ReactNode; testId: string;
}) {
  return (
    <Card className="scroll-mt-24 p-4" data-testid={testId} id={`overview-${id}`}>
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-ui-title font-semibold text-ink">{title}</h3>
        {count !== undefined ? <span className="rounded-full bg-surface-muted px-2 py-0.5 text-ui-meta tabular-nums text-muted">{count}</span> : null}
      </div>
      <div className="mt-3">{children}</div>
    </Card>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-ui-body text-muted">{children}</p>;
}

function Header({ snap }: { snap: LiveSnapshot }) {
  return (
    <Card className="scroll-mt-24 px-4 py-3" data-testid="live-header" id="overview-header">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-display text-ui-title font-semibold text-ink">Odoo {snap.server_version || snap.major}</h2>
        <Badge>{EDITION_COPY[snap.edition] ?? snap.edition}</Badge>
        <Badge>{HOSTING_COPY[snap.hosting] ?? snap.hosting}</Badge>
        {snap.support !== "supported" ? <Badge variant="warning">Support: {snap.support}</Badge> : null}
      </div>
      <p className="mt-1 text-ui-meta text-muted">
        {snap.counts.models} models · {snap.counts.apps} apps · {snap.counts.modules} modules installed
        {snap.counts.modules_hidden ? ` (${snap.counts.modules_hidden} localisation/theme/test modules hidden)` : ""}
      </p>
      {snap.problems.length ? (
        <p className="mt-1 text-ui-meta text-muted" data-testid="live-partial">
          {`Some details couldn't be read: ${snap.problems.slice(0, 2).join("; ")}`}
        </p>
      ) : null}
    </Card>
  );
}

function Capabilities({ snap, extras, connectionId }: { snap: LiveSnapshot; extras?: React.ReactNode; connectionId: string }) {
  const code = gate(snap, "python_module_install", "module_deploy");
  const yes = snap.can_change.filter((c) => c.available === "yes");
  const no = snap.can_change.filter((c) => c.available !== "yes");
  return (
    <SectionCard id="capabilities" title="What you can change here" testId="live-can-change">
      {snap.can_change.length === 0 ? (
        <Empty>{"We couldn't work out what this plan allows yet. Run a connection check to find out."}</Empty>
      ) : (
        <ul className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
          {[...yes, ...no].map((c) => (
            <li key={c.key} className="flex items-start gap-2 text-ui-body" title={c.reason}>
              <span aria-hidden className={`mt-1.5 size-1.5 shrink-0 rounded-full ${c.available === "yes" ? "bg-status-ok" : "border border-border-strong"}`} />
              <span className={c.available === "yes" ? "text-ink" : "text-muted"}>
                {CHANGE_COPY[c.key] ?? c.key}
                {c.available !== "yes" ? ` · ${availabilityLabel(c.available)}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-4 border-t border-border-subtle pt-3" data-testid="custom-code">
        {code.allowed ? (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-ui-meta text-muted">Write a custom module, test it on a copy, then promote it here.</p>
            <Link href={`/connections/${connectionId}/code-studio`} data-testid="build-custom-code"
              className="text-ui-body font-medium text-accent hover:underline">Build custom code <span aria-hidden>→</span></Link>
          </div>
        ) : <LockedNote what="Custom code" gate={code} testId="custom-code-locked" />}
      </div>
      {extras}
    </SectionCard>
  );
}

export function LiveSnapshotView({ snap, connectionId, capabilityExtras, onApplied = () => {} }: {
  snap: LiveSnapshot; connectionId: string; capabilityExtras?: React.ReactNode;
  /** Re-read the snapshot (server cache dropped) after any Apply. */
  onApplied?: () => void;
}) {
  const url = useExplorerUrl();
  const [fix, setFix] = useState<{ kind: FixKind; model: string; label: string } | null>(null);
  const fixGates: Record<FixKind, Gate> = {
    access: gate(snap, "security_acl_rules"),
    menu: gate(snap, "menus_actions"),
  };
  const explorerGates: ExplorerGates = {
    field: gate(snap, "custom_fields"),
    view: gate(snap, "xpath_inherit", "views_community"),
    automation: gate(snap, "base_automation"),
    access: fixGates.access,
    menu: fixGates.menu,
    code: gate(snap, "python_module_install", "module_deploy"),
  };
  const labelOf = (model: string) => snap.custom_models.find((m) => m.model === model)?.label || model;
  const fixLabel = (item: AttentionItem) => {
    const kind = fixKindFor(item);
    if (!kind || !item.drill.model || !fixGates[kind].allowed) return null;
    return kind === "access" ? "Add access rules" : "Add menu";
  };
  const goTo = useCallback((section: OverviewSectionId) => goToSection(`overview-${section}`), []);
  const drill = useCallback((item: AttentionItem) => {
    if (item.drill.section === "explorer" && item.drill.model) {
      url.set({ model: item.drill.model, tab: item.drill.tab ?? "fields" }, "push");
    }
    goTo(item.drill.section);
  }, [goTo, url]);
  const openModel = (model: string) => {
    url.set({ model, tab: "fields" }, "push");
    goTo("explorer");
  };
  useEffect(() => {
    // '/' focuses the explorer search, unless the user is already typing somewhere.
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      const input = document.getElementById("overview-explorer-search");
      if (!input) return;
      e.preventDefault();
      input.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <div className="space-y-4" data-testid="live-snapshot">
      <Header snap={snap} />
      <AttentionStrip
        items={snap.attention ?? []}
        onDrill={drill}
        fixLabel={fixLabel}
        onFix={(item) => {
          const kind = fixKindFor(item);
          if (kind && item.drill.model) setFix({ kind, model: item.drill.model, label: labelOf(item.drill.model) });
        }}
      />
      {fix ? (
        <AttentionFix
          key={`${fix.kind}:${fix.model}`}
          connectionId={connectionId}
          kind={fix.kind}
          model={fix.model}
          label={fix.label}
          onCancel={() => setFix(null)}
          onDone={() => { setFix(null); onApplied(); }}
        />
      ) : null}
      <SummaryCards snap={snap} onDrill={goTo} />
      <div className="grid gap-3 lg:grid-cols-3">
        <SectionCard id="apps" title="Installed apps" count={snap.counts.apps} testId="live-apps">
          {snap.apps.length === 0 ? (
            <Empty>No apps installed yet, only technical modules.</Empty>
          ) : (
            <ul className="flex flex-wrap gap-1.5">
              {snap.apps.map((a) => <li key={a.name}><Badge>{a.label || a.name}</Badge></li>)}
            </ul>
          )}
          <div className="mt-3"><AppInstaller connectionId={connectionId} onInstalled={onApplied} /></div>
        </SectionCard>
        <SectionCard id="custom-models" title="Custom models" count={snap.counts.custom_models} testId="live-custom-models">
          {snap.custom_models.length === 0 ? (
            <Empty>Nothing custom yet. Models you build in App Studio show up here.</Empty>
          ) : (
            <ul className="space-y-0.5 text-ui-body">
              {snap.custom_models.slice(0, 12).map((m) => (
                <li key={m.model}>
                  <button type="button" onClick={() => openModel(m.model)}
                    className="flex w-full justify-between gap-2 rounded px-1 py-0.5 text-left hover:bg-surface-muted">
                    <span className="truncate text-ink">{m.label}</span>
                    <span className="text-ui-mono text-muted">{m.model}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
        <SectionCard
          id="automations"
          title="Automations and scheduled actions"
          count={snap.counts.automations + snap.counts.scheduled_actions}
          testId="live-automations"
        >
          {snap.automations.length + snap.scheduled_actions.length === 0 ? (
            <Empty>No automations or <Term tech="ir.cron">scheduled actions</Term> yet.</Empty>
          ) : (
            <ul className="space-y-1 text-ui-body">
              {snap.automations.slice(0, 8).map((a, i) => (
                <li key={`a${i}`} className="flex justify-between gap-2">
                  <span className="truncate text-ink">{a.name}</span>
                  <span className="text-ui-meta text-muted">{a.model_id || a.trigger}</span>
                </li>
              ))}
              {snap.scheduled_actions.slice(0, 8).map((c, i) => (
                <li key={`c${i}`} className="flex justify-between gap-2">
                  <span className="truncate text-ink">{c.cron_name || c.name}</span>
                  <span className="text-ui-meta text-muted">
                    every {c.interval_number} {c.interval_type}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      </div>
      <Capabilities snap={snap} extras={capabilityExtras} connectionId={connectionId} />
      <ModelExplorer
        connectionId={connectionId}
        models={snap.models}
        model={url.model}
        tab={url.tab}
        onSelect={(model) => url.set({ model, tab: "fields" }, "push")}
        onTab={(tab) => url.model && url.set({ model: url.model, tab }, "replace")}
        gates={explorerGates}
        onApplied={onApplied}
      />
    </div>
  );
}

/** Overview "live database" picture. Read-only; edit entry points come in job 2. */
export function LiveDatabaseSection({ connectionId, onSnapshot, capabilityExtras }: {
  connectionId: string;
  /** Lets the page derive counts (e.g. the first-run card) from the same snapshot. */
  onSnapshot?: (snap: LiveSnapshot) => void;
  capabilityExtras?: React.ReactNode;
}) {
  const { state, reload, refresh } = useLiveSnapshot(connectionId);
  const ready = state.status === "ready" ? state.data : null;
  useEffect(() => {
    if (ready) onSnapshot?.(ready);
  }, [ready, onSnapshot]);
  return (
    <section className="mt-6" aria-label="Live database" data-testid="overview-live-db">
      {state.status === "loading" ? (
        <div className="space-y-3" data-testid="live-loading" aria-busy>
          <Skeleton className="h-16" />
          <Skeleton className="h-14" />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Skeleton className="h-24" /><Skeleton className="h-24" /><Skeleton className="h-24" /><Skeleton className="h-24" />
          </div>
        </div>
      ) : state.status === "error" ? (
        <EmptyState
          title="Couldn't reach your database"
          description={`${state.message} Nothing here changes Odoo, so it's safe to try again.`}
          action={<Button variant="secondary" size="sm" onClick={reload}>Try again</Button>}
        />
      ) : (
        <LiveSnapshotView snap={state.data} connectionId={connectionId} capabilityExtras={capabilityExtras} onApplied={refresh} />
      )}
    </section>
  );
}
