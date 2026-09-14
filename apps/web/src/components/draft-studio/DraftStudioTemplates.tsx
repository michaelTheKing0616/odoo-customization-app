"use client";

import Link from "next/link";
import { AskWhyButton } from "@/components/expert/AskWhyButton";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Card } from "@/components/ui/layout-primitives";
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
  onOpenTemplate: (tpl: AppTemplate) => void;
  templateScaffoldOpts: (id: string) => { requireObjectWrite?: true };
};

export function DraftStudioTemplates({
  connectionId,
  connection,
  templates,
  selectedId,
  result,
  onOpenTemplate,
  templateScaffoldOpts,
}: DraftStudioTemplatesProps) {
  return (
    <section className="mt-10 border-t border-border-subtle pt-8">
      <h2 className="text-lg font-semibold text-ink">Ready-made templates</h2>
      <p className="mt-1 text-sm text-muted">
        Skip AI — one click scaffolds a full app (Library, CRM Lite, …) directly on this connection.
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
              className={`rounded-md border p-4 text-left transition ${
                !canScaffold
                  ? "cursor-not-allowed border-border-subtle bg-surface-muted opacity-50"
                  : active
                    ? "border-accent bg-accent-subtle"
                    : "border-border-subtle bg-surface-raised hover:bg-surface-muted"
              }`}
            >
              <p className="text-lg font-semibold text-ink">{tpl.name}</p>
              <p className="mt-1 font-mono text-xs text-accent">{tpl.id}</p>
              <p className="mt-2 text-sm text-muted">{tpl.description}</p>
              {blocked ? <p className="mt-2 text-xs text-warning">{blocked}</p> : null}
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
                {result.models.length > 0 ? ` (${result.models.length})` : " — none reported"}
                {result.models_skipped && result.models_skipped.length > 0
                  ? ` · skipped: ${result.models_skipped.join(", ")}`
                  : ""}
              </span>
            </li>
            <li className="flex items-start gap-2 rounded-md border border-border-subtle px-3 py-2">
              <span aria-hidden>{(result.menus_created ?? 0) > 0 ? "✓" : "○"}</span>
              <span>
                Menus created
                {typeof result.menus_created === "number" ? ` (${result.menus_created})` : " — n/a"}
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
