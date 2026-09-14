"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import type { SnapshotRow } from "@/lib/api";

const BUILDER_TYPES = new Set(["field", "model"]);

type BuilderSnapshotsProps = {
  connectionId: string;
  snapshots: SnapshotRow[];
  busy?: boolean;
  onRollback: (snapshotId: string) => void;
};

export function BuilderSnapshots({
  connectionId,
  snapshots,
  busy,
  onRollback,
}: BuilderSnapshotsProps) {
  const scoped = snapshots.filter((s) => BUILDER_TYPES.has(s.resource_type));
  const rows = scoped.length ? scoped : snapshots.filter((s) => s.resource_type === "field");

  return (
    <section className="mt-8 space-y-3" data-testid="builder-snapshots">
      <div>
        <h2 className="text-sm font-semibold text-ink">Snapshots</h2>
        <p className="mt-1 text-xs text-muted">
          Restore points taken before field or model deletes. Definitions restore when Odoo allows
          it — dropped columns are only partially recoverable.
        </p>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-muted">
          No model or field snapshots yet. They appear when you deprecate or delete.
        </p>
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
