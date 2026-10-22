import type { Gate } from "./gates";

/** A locked action is never hidden: say plainly why it isn't available. */
export function LockedNote({ what, gate, testId }: { what: string; gate: Gate; testId?: string }) {
  return (
    <p className="flex items-start gap-1.5 text-ui-meta text-muted" data-testid={testId ?? "locked-note"}>
      <span aria-hidden className="mt-1.5 size-1.5 shrink-0 rounded-full border border-border-strong" />
      <span><span className="text-ink">{what}</span> isn&apos;t available here. {gate.reason}</span>
    </p>
  );
}
