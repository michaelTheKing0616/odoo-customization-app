"use client";

import Link from "next/link";
import { AskWhyButton } from "@/components/expert/AskWhyButton";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card, Skeleton } from "@/components/ui/layout-primitives";
import type { AppTemplate, Connection, ScaffoldResult } from "@/lib/api";
import {
  scaffoldApplyAllowed,
  scaffoldApplyBlockedReason,
} from "@/lib/capabilities";

type DraftStudioTemplatesProps = {
  connectionId: string;
  connection: Connection | null;
  templates: AppTemplate[];
  selectedId?: string | null;
  result: ScaffoldResult | null;
  /** Templates and capabilities still loading: skeleton cards, no locked flash. */
  loading?: boolean;
  onOpenTemplate: (tpl: AppTemplate) => void;
  templateScaffoldOpts: (id: string) => { requireObjectWrite?: true };
};

export function DraftStudioTemplates({
  connectionId,
  connection,
  templates,
  selectedId,
  result,
  loading = false,
  onOpenTemplate,
  templateScaffoldOpts,
}: DraftStudioTemplatesProps) {
  const capabilitiesUnknown = !loading && Boolean(connection) && !connection?.capabilities;
  return (
    <section
      className="draft-studio-templates"
      aria-labelledby="draft-studio-templates-title"
      data-testid="draft-studio-templates"
    >
      <h2 id="draft-studio-templates-title" className="draft-studio-section-title">
        Ready-made templates
      </h2>
      <p className="draft-studio-section-lede">
        Skip AI. One click scaffolds a full app (Library, CRM Lite, and more) directly on
        this connection, after you confirm.
      </p>
      {capabilitiesUnknown && templates.length > 0 ? (
        <p className="draft-studio-templates-locked" data-testid="templates-capabilities-unknown">
          Templates stay locked until this connection is probed. Open Connect, re-probe
          the connection, then come back to scaffold.{" "}
          <Link href="/connect" className="font-medium text-ink underline underline-offset-2">
            Open Connect
          </Link>
        </p>
      ) : null}
      {loading ? (
        <div
          className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
          role="status"
          aria-label="Loading templates"
          data-testid="templates-loading"
        >
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ) : null}
      {!loading && templates.length === 0 ? (
        <p className="draft-studio-quiet-note mt-3" data-testid="templates-empty">
          No templates loaded for this connection. Describe the app above instead.
        </p>
      ) : null}
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4" hidden={loading}>
        {templates.map((tpl) => {
          const active = selectedId === tpl.id;
          const opts = templateScaffoldOpts(tpl.id);
          const canScaffold = scaffoldApplyAllowed(connection, opts);
          const blocked = scaffoldApplyBlockedReason(connection, opts);
          return (
            <button
              key={tpl.id}
              type="button"
              data-testid={`template-card-${tpl.id}`}
              disabled={!canScaffold}
              title={blocked ?? undefined}
              onClick={() => {
                if (!canScaffold) return;
                onOpenTemplate(tpl);
              }}
              aria-pressed={active}
              className={`draft-studio-template${!canScaffold ? " is-locked" : ""}${
                active ? " is-selected" : ""
              }`}
            >
              <span className="draft-studio-template-name">{tpl.name}</span>
              <span className="draft-studio-template-id">{tpl.id}</span>
              <span className="draft-studio-template-desc">{tpl.description}</span>
              {blocked && !capabilitiesUnknown ? (
                <span className="draft-studio-template-blocked">{blocked}</span>
              ) : null}
            </button>
          );
        })}
      </div>
      {result ? (
        <Card className="mt-8 p-5" data-testid="scaffold-result">
          <h2 className="text-lg font-semibold text-ink">Scaffold result</h2>
          <p className="mt-2 text-sm text-ink">
            {result.ok ? "Complete" : "Partial"} · {result.message}
          </p>
          <p className="mt-1 text-sm text-muted">
            Template <code className="font-mono text-accent">{result.template_id}</code> ·{" "}
            {result.fields_created} fields created
            {typeof result.view_injects === "number" ? ` · ${result.view_injects} view inject(s)` : ""}
          </p>
          {result.warnings && result.warnings.length > 0 ? (
            <Callout variant="warning" title="Warnings" className="mt-3">
              <ul className="list-disc space-y-1 pl-5">
                {result.warnings.map((w, i) => (
                  <li key={`${i}-${w}`}>{w}</li>
                ))}
              </ul>
            </Callout>
          ) : null}
          <ol data-testid="scaffold-checklist" className="mt-5 space-y-2 text-sm">
            <li className="flex items-start gap-2 rounded-md border border-border-subtle px-3 py-2">
              <span aria-hidden>{result.models.length > 0 ? "✓" : "○"}</span>
              <span>
                Models created
                {result.models.length > 0 ? ` (${result.models.length})` : " (none reported)"}
                {result.models_skipped && result.models_skipped.length > 0
                  ? ` · skipped: ${result.models_skipped.join(", ")}`
                  : ""}
              </span>
            </li>
            <li className="flex items-start gap-2 rounded-md border border-border-subtle px-3 py-2">
              <span aria-hidden>{(result.menus_created ?? 0) > 0 ? "✓" : "○"}</span>
              <span>
                Menus created
                {typeof result.menus_created === "number" ? ` (${result.menus_created})` : " (n/a)"}
              </span>
            </li>
            <li className="flex items-start gap-2 rounded-md border border-border-subtle px-3 py-2">
              <span aria-hidden>→</span>
              <Link
                href={
                  result.models[0]
                    ? `/connections/${connectionId}/designer?model=${encodeURIComponent(result.models[0])}`
                    : `/connections/${connectionId}/designer`
                }
                className="text-muted hover:underline"
              >
                Open designer
              </Link>
            </li>
            <li className="flex items-start gap-2 rounded-md border border-border-subtle px-3 py-2">
              <span aria-hidden>→</span>
              <Link href={`/connections/${connectionId}`} className="text-muted hover:underline">
                Run sandbox
              </Link>
              <span className="text-muted">(on connection page)</span>
            </li>
          </ol>
          <ul data-testid="scaffold-models" className="mt-4 space-y-2 text-sm">
            {result.models.map((model) => (
              <li
                key={model}
                className="flex flex-wrap items-center gap-3 rounded-md border border-border-subtle px-3 py-2"
              >
                <span className="font-mono text-muted">{model}</span>
                <AskWhyButton subject={model} context={`Scaffold created model ${model}`} />
                <Link
                  href={`/connections/${connectionId}/builder`}
                  className="text-xs text-muted hover:underline"
                >
                  Builder
                </Link>
                <Link
                  href={`/connections/${connectionId}/designer?model=${encodeURIComponent(model)}`}
                  className="text-xs text-muted hover:underline"
                >
                  Designer
                </Link>
              </li>
            ))}
            {result.models.length === 0 ? <li className="text-muted">No models reported.</li> : null}
          </ul>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button variant="secondary" asChild>
              <Link href={`/connections/${connectionId}`}>Back to overview</Link>
            </Button>
            <Button variant="primary" asChild>
              <Link href={`/connections/${connectionId}/builder`}>Open builder</Link>
            </Button>
          </div>
        </Card>
      ) : null}
    </section>
  );
}
