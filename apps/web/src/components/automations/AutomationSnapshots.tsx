"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import type { SnapshotRow } from "@/lib/api";

type AutomationSnapshotsProps = {
  connectionId: string;
  snapshots: SnapshotRow[];
  busy?: boolean;
  onRollback: (snapshotId: string) => void;
};

export function AutomationSnapshots({
  connectionId,
  snapshots,
  busy,
  onRollback,
}: AutomationSnapshotsProps) {
  const autoSnaps = snapshots.filter(
    (s) => s.resource_type === "automation" || s.resource_type === "server_action",
  );
  const rows = autoSnaps.length ? autoSnaps : snapshots;

  return (
    <section className="mt-8 space-y-3" data-testid="automations-snapshots">
      <div>
        <h2 className="text-sm font-semibold text-ink">Snapshots</h2>
        <p className="mt-1 text-xs text-muted">
          Restores the automation definition when possible. Does not rewind business data.
        </p>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-muted">No snapshots yet. They appear when you create or delete a rule.</p>
      ) : (
        <ul className="space-y-2">
          {rows.slice(0, 8).map((s) => (
            <li key={s.id}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-3">
                <div className="min-w-0">
                  <p className="truncate text-sm text-ink">{s.label}</p>
                  <p className="text-xs text-muted">
                    {s.resource_type} · {s.reversible} · {s.created_at}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={busy || s.reversible === "no"}
                  onClick={() => onRollback(s.id)}
                >
                  Undo
                </Button>
              </Card>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-muted">
        Full journal:{" "}
        <Link href={`/connections/${connectionId}/journal`} className="text-accent hover:underline">
          Change journal
        </Link>
      </p>
    </section>
  );
}
