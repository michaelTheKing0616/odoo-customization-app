"use client";

import { Card } from "@/components/ui/layout-primitives";
import type { AttentionItem, LiveSnapshot, OverviewSectionId } from "@/lib/api";

type Tone = "critical" | "warning" | "neutral";
type Summary = { id: OverviewSectionId; label: string; value: number; story: string; tone: Tone };

const STORY_TONE: Record<Tone, string> = {
  critical: "text-status-critical-strong", warning: "text-status-warning-strong", neutral: "text-muted",
};
const DOT_TONE: Record<Tone, string> = { critical: "bg-status-critical", warning: "bg-status-warning", neutral: "" };

function count(items: AttentionItem[], key: string): number {
  return items.find((i) => i.key === key)?.count ?? 0;
}

export function summaries(snap: LiveSnapshot): Summary[] {
  const a = snap.attention;
  const noMenu = count(a, "custom_no_menu");
  const noAccess = count(a, "custom_no_access");
  const failing = count(a, "failing_crons") + count(a, "overdue_crons") + count(a, "orphan_automations");
  const pending = count(a, "pending_modules") + count(a, "broken_modules");
  const customStory = [noAccess ? `${noAccess} without access rules` : "", noMenu ? `${noMenu} without a menu` : ""]
    .filter(Boolean).join(", ");
  return [
    { id: "apps", label: "Apps", value: snap.counts.apps,
      story: pending ? pending === 1 ? "1 module needs a look" : `${pending} modules need a look` : `${snap.counts.modules} modules installed`,
      tone: count(a, "broken_modules") ? "critical" : "neutral" },
    { id: "custom-models", label: "Custom models", value: snap.counts.custom_models,
      story: snap.counts.custom_models ? customStory || "All reachable and secured" : "Nothing custom yet",
      tone: noAccess + noMenu ? "warning" : "neutral" },
    { id: "automations", label: "Automations and scheduled actions",
      value: snap.counts.automations + snap.counts.scheduled_actions,
      story: failing ? `${failing} not running as expected` : `${snap.counts.automations} automations, ${snap.counts.scheduled_actions} scheduled`,
      tone: failing ? "critical" : "neutral" },
    { id: "explorer", label: "Models", value: snap.counts.models, story: "Browse any model's structure", tone: "neutral" },
  ];
}

/** Stripe-pattern summary cards: a number, a one-line story, and a drill-down. */
export function SummaryCards({ snap, onDrill }: {
  snap: LiveSnapshot; onDrill: (section: OverviewSectionId) => void;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" data-testid="summary-cards">
      {summaries(snap).map((s) => (
        <Card key={s.id} className="p-0 transition-colors hover:border-border-strong motion-reduce:transition-none">
          <button type="button" onClick={() => onDrill(s.id)} data-testid={`summary-${s.id}`}
            className="group flex h-full w-full flex-col rounded-md p-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">
            <span className="flex items-center justify-between text-ui-label font-medium text-muted">
              {s.label}
              <span aria-hidden className="text-subtle opacity-0 transition-opacity duration-150 ease-out group-hover:opacity-100 motion-reduce:transition-none">→</span>
            </span>
            <span className="mt-2 font-display text-3xl font-semibold tabular-nums tracking-tight text-ink">{s.value}</span>
            <span className={`mt-auto flex items-center gap-1.5 pt-2 text-ui-meta ${STORY_TONE[s.tone]}`}>
              {s.tone !== "neutral" ? <span aria-hidden className={`size-1.5 rounded-full ${DOT_TONE[s.tone]}`} /> : null}
              {s.story}
            </span>
          </button>
        </Card>
      ))}
    </div>
  );
}
