"use client";

import { Card } from "@/components/ui/layout-primitives";
import type { AttentionItem, AttentionSeverity } from "@/lib/api";

const TONE: Record<AttentionSeverity, { label: string; rail: string; dot: string; pill: string }> = {
  critical: { label: "Broken", rail: "bg-status-critical", dot: "bg-status-critical",
    pill: "bg-status-critical-subtle text-status-critical-strong" },
  warning: { label: "Needs setup", rail: "bg-status-warning", dot: "bg-status-warning",
    pill: "bg-status-warning-subtle text-status-warning-strong" },
  limit: { label: "Plan limit (estimate)", rail: "bg-status-notice", dot: "bg-status-notice",
    pill: "bg-status-notice-subtle text-status-notice-strong" },
  notice: { label: "Heads up", rail: "bg-status-notice", dot: "bg-status-notice",
    pill: "bg-status-notice-subtle text-status-notice-strong" },
};

export const ALL_CLEAR =
  "Nothing needs your attention. We checked scheduled actions, modules, custom models and your plan.";

function tally(items: AttentionItem[]): string {
  const n = (s: AttentionSeverity) => items.filter((i) => i.severity === s).length;
  return [
    n("critical") ? `${n("critical")} broken` : "",
    n("warning") ? `${n("warning")} need setup` : "",
    n("limit") + n("notice") ? `${n("limit") + n("notice")} to know about` : "",
  ].filter(Boolean).join(" · ");
}

/** Ranked "Needs attention" list (SPEC §2): calm but visible. One calm line when empty. */
export function AttentionStrip({ items, onDrill, fixLabel, onFix }: {
  items: AttentionItem[];
  onDrill: (item: AttentionItem) => void;
  /** Direct fix for an item when one exists (e.g. "Add access rules"); null = none. */
  fixLabel?: (item: AttentionItem) => string | null;
  onFix?: (item: AttentionItem) => void;
}) {
  if (items.length === 0) {
    return (
      <Card className="flex items-center gap-3 px-4 py-3" data-testid="attention-clear" role="status">
        <span aria-hidden className="size-2 shrink-0 rounded-full bg-status-ok" />
        <p className="text-ui-body text-ink">{ALL_CLEAR}</p>
      </Card>
    );
  }
  return (
    <Card className="overflow-hidden p-0" data-testid="attention" aria-labelledby="attention-title">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border-subtle px-4 py-3">
        <h2 id="attention-title" className="text-ui-title font-semibold text-ink">Needs attention</h2>
        <p className="text-ui-meta text-muted">{tally(items)}</p>
      </div>
      <ol className="divide-y divide-border-subtle">
        {[...items].sort((a, b) => a.rank - b.rank).map((item) => {
          const t = TONE[item.severity];
          return (
            <li key={item.key} className="relative flex flex-wrap items-start gap-x-4 gap-y-2 py-3 pl-5 pr-4"
              data-severity={item.severity}>
              <span aria-hidden className={`absolute inset-y-0 left-0 w-[3px] ${t.rail}`} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-ui-meta font-medium ${t.pill}`}>
                    <span aria-hidden className={`size-1.5 rounded-full ${t.dot}`} />{t.label}
                  </span>
                  <p className="text-ui-body font-medium text-ink">{item.title}</p>
                </div>
                <p className="mt-1 text-ui-meta text-muted">{item.detail}</p>
                {item.names.length ? (
                  <ul className="mt-1.5 flex flex-wrap gap-1" aria-label="Affected">
                    {item.names.slice(0, 6).map((n) => (
                      <li key={n} className="rounded border border-border-subtle bg-surface-muted px-1.5 py-0.5 font-mono text-ui-mono text-muted">{n}</li>
                    ))}
                    {item.names.length > 6 ? <li className="px-1 text-ui-meta text-muted">+{item.names.length - 6} more</li> : null}
                  </ul>
                ) : null}
              </div>
              {fixLabel && onFix && fixLabel(item) ? (
                <button type="button" onClick={() => onFix(item)} data-testid={`fix-${item.key}`}
                  className="shrink-0 rounded-md border border-border-subtle px-2 py-1 text-ui-body font-medium text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
                  {fixLabel(item)}
                </button>
              ) : null}
              <button type="button" onClick={() => onDrill(item)}
                className="shrink-0 rounded-md px-2 py-1 text-ui-body font-medium text-accent hover:bg-accent-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
                {item.drill.section === "explorer" ? "Open model" : "Show"} <span aria-hidden>→</span>
              </button>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
