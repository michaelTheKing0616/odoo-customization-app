"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import type { BotApproval } from "@/lib/api/bot-approvals";

type Props = {
  item: BotApproval;
  busy?: "approve" | "reject" | null;
  error?: string | null;
  /** Another decision is in flight: lock these buttons too. */
  locked?: boolean;
  onApprove?: (id: string) => void;
  onReject?: (id: string) => void;
};

const TIER_VARIANT = { 1: "success", 2: "warning", 3: "danger" } as const;

const STATUS_TEXT: Record<BotApproval["status"], string> = {
  auto: "Runs on its own",
  pending: "Waiting for you",
  approved: "Approved",
  rejected: "Rejected",
  refused: "Can't run",
};

function plural(n: number, word: string) {
  return `${n.toLocaleString()} ${word}${n === 1 ? "" : "s"}`;
}

/** One bot plan: what changes, how many records, why it needs this level, and how to undo. */
export function BotApprovalCard({
  item,
  busy = null,
  error = null,
  locked = false,
  onApprove,
  onReject,
}: Props) {
  const { card } = item;
  const refused = item.status === "refused" || card.tier === null;
  const pending = item.status === "pending" && !refused;
  const headingId = `bot-approval-${item.id}`;

  return (
    <article
      aria-labelledby={headingId}
      data-testid="bot-approval-card"
      className="flex flex-col gap-4 rounded-xl border border-border-subtle bg-surface p-5"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex flex-col gap-1">
          <h3 id={headingId} className="font-medium text-ink">
            {card.summary || "Bot change"}
          </h3>
          <p className="text-sm text-muted" data-testid="bot-approval-count">
            Changes exactly {plural(card.records, "record")}, never more.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {refused ? (
            <Badge variant="danger">Can&apos;t run</Badge>
          ) : (
            <Badge variant={TIER_VARIANT[card.tier as 1 | 2 | 3]}>
              <span data-testid="bot-approval-tier">Level {card.tier}</span>
            </Badge>
          )}
          <Badge>{STATUS_TEXT[item.status]}</Badge>
        </div>
      </header>

      {refused ? (
        <Callout
          variant="danger"
          title="Ingenium won't run this"
          testId="bot-approval-refusal"
        >
          {card.refusal ||
            "We couldn't prove this change is safe, so it won't run."}{" "}
          Nothing in your database has changed.
        </Callout>
      ) : (
        <section aria-label="Why this level" className="flex flex-col gap-2">
          <p className="text-sm font-medium text-ink">{card.tier_label}</p>
          <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-muted">
            {card.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </section>
      )}

      {card.changes.length > 0 && (
        <section
          aria-label="What will change"
          className="flex flex-col gap-1 text-sm"
        >
          <p className="font-medium text-ink">What will change</p>
          <ul className="flex flex-col gap-1 text-muted">
            {card.changes.map((c) => (
              <li key={c.field}>
                <span className="text-ink">{c.field}</span> becomes{" "}
                {c.to || "empty"}
              </li>
            ))}
          </ul>
        </section>
      )}

      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div className="flex flex-col gap-0.5">
          <dt className="text-muted">Undo</dt>
          <dd className="text-ink" data-testid="bot-approval-undo">
            {card.undo.available ? card.undo.how : "Not available"}
          </dd>
        </div>
        <div className="flex flex-col gap-0.5">
          <dt className="text-muted">Practice run on a copy</dt>
          <dd className="text-ink">
            {card.rehearsal.passed ? "Passed" : "Not done"}
          </dd>
        </div>
      </dl>

      {!refused && card.limits.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted">
            What undo doesn&apos;t cover
          </summary>
          <ul className="mt-2 flex list-disc flex-col gap-1 pl-5 text-muted">
            {card.limits.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </details>
      )}

      {error && (
        <Callout
          variant="warning"
          title="That didn't go through"
          testId="bot-approval-error"
        >
          {error}
        </Callout>
      )}

      {pending && (onApprove || onReject) && (
        <footer className="flex flex-wrap gap-2">
          {onApprove && (
            <Button
              variant="primary"
              loading={busy === "approve"}
              disabled={locked || busy !== null}
              onClick={() => onApprove(item.id)}
            >
              Approve {plural(card.records, "change")}
            </Button>
          )}
          {onReject && (
            <Button
              variant="ghost"
              loading={busy === "reject"}
              disabled={locked || busy !== null}
              onClick={() => onReject(item.id)}
            >
              Reject
            </Button>
          )}
        </footer>
      )}
    </article>
  );
}
