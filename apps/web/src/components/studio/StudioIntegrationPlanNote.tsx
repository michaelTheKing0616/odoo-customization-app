"use client";

import type { IntegrationPlan } from "@/lib/integration-plan";
import { pythonBlockedOnHost } from "@/lib/integration-plan";

type StudioIntegrationPlanNoteProps = {
  plan: IntegrationPlan | null;
};

const COLLAPSE_AFTER = 3;

function listLabels(labels: string[]): string {
  if (labels.length <= 1) return labels.join("");
  return `${labels.slice(0, -1).join(", ")} and ${labels[labels.length - 1]}`;
}

/**
 * One quiet note under the generate result: what the build uses, what waits
 * for an install, what was left out (and how to add it), and what needs the
 * Option A lane. Amber only for left out and Option A risk.
 */
export function StudioIntegrationPlanNote({ plan }: StudioIntegrationPlanNoteProps) {
  if (!plan) return null;
  const available = plan.integrations.filter((i) => i.status === "available");
  const deferred = plan.integrations.filter((i) => i.status === "deferred" || i.status === "unchecked");
  const leftOut = plan.integrations.filter((i) => i.status === "left_out");
  const pieces = plan.python_pieces || [];
  const blocked = pieces.some(pythonBlockedOnHost);
  const rows = deferred.length + leftOut.length + (pieces.length ? 1 : 0);
  if (rows === 0 && available.length === 0) return null;
  const risky = leftOut.length > 0 || pieces.length > 0;

  const headline =
    rows === 0
      ? "Built the core app with every app it links to."
      : `Built the core app. ${rows} ${rows === 1 ? "thing needs" : "things need"} your attention.`;

  return (
    <details
      className="studio-plan-note"
      data-testid="studio-integration-plan"
      data-tone={risky ? "amber" : "quiet"}
      open={rows <= COLLAPSE_AFTER}
    >
      <summary className="studio-plan-note-summary">
        <span className="studio-plan-note-dot" aria-hidden />
        <span className="studio-plan-note-headline">{headline}</span>
      </summary>
      <ul className="studio-plan-note-list">
        {available.length > 0 ? (
          <li data-status="available" data-testid="studio-plan-available">
            <span className="studio-plan-note-key">Linked</span>
            <span>Uses {listLabels(available.map((i) => i.app_label))}.</span>
          </li>
        ) : null}
        {deferred.map((item) => (
          <li key={item.module} data-status="deferred" data-testid={`studio-plan-${item.module}`}>
            <span className="studio-plan-note-key">Install later</span>
            <span>{item.note || `Install ${item.app_label}, then refine to add it.`}</span>
          </li>
        ))}
        {leftOut.map((item) => (
          <li key={item.module} data-status="left_out" data-testid={`studio-plan-${item.module}`}>
            <span className="studio-plan-note-key">Left out</span>
            <span>{item.note || `${item.app_label} is not available on this database.`}</span>
          </li>
        ))}
        {pieces.length > 0 ? (
          <li data-status="option_a" data-testid="studio-plan-option-a">
            <span className="studio-plan-note-key">Custom code</span>
            <span>
              {listLabels(pieces.map((p) => p.label))} {pieces.length === 1 ? "needs" : "need"} custom
              Python. {blocked
                ? "They are authored as a module, proved in a sandbox, then published by a person on Odoo.sh or a self-hosted server. They cannot install on Odoo Online."
                : "They are authored as a module, proved in a sandbox, then published by a person."}
            </span>
          </li>
        ) : null}
      </ul>
    </details>
  );
}
