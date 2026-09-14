"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";
import type { SnapshotRow } from "@/lib/api";
import {
  canRollbackSnapshot,
  journalHref,
  snapshotReversibilityLabel,
  snapshotsForProject,
  type ProjectRow,
} from "@/lib/projects-journey";

type ProjectHistoryProps = {
  connectionId: string;
  project: ProjectRow | null;
  snapshots: SnapshotRow[];
  busy?: boolean;
  onRollback: (snapshotId: string) => void;
};

export function ProjectHistory({
  connectionId,
  project,
  snapshots,
  busy,
  onRollback,
}: ProjectHistoryProps) {
  const rows = snapshotsForProject(snapshots, project).slice(0, 8);

  return (
    <section className="space-y-3" data-testid="projects-history">
      <div>
        <h2 className="text-sm font-semibold text-ink">Snapshot history</h2>
        <p className="mt-1 text-xs text-muted">
          Restore points from this connection. Rollback restores views and automations when Odoo
          allows. Created columns are only partially recoverable.
        </p>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-muted" data-testid="projects-history-empty">
          No snapshots yet. They appear before risky writes. Apply still needs a human confirm.
        </p>
      ) : (
        <ul className="project-history-list">
          {rows.map((snapshot) => {
            const canRollback = canRollbackSnapshot(snapshot.reversible);
            return (
              <li key={snapshot.id}>
                <Card className="flex flex-wrap items-center justify-between gap-3 p-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-1">
                      <Badge variant="info">Snapshot</Badge>
                      <Badge variant={snapshot.reversible === "yes" ? "success" : "warning"}>
                        {snapshotReversibilityLabel(snapshot.reversible)}
                      </Badge>
                    </div>
                    <p className="mt-1 truncate text-sm text-ink">{snapshot.label}</p>
                    <p className="font-mono text-[11px] text-muted">
                      {snapshot.resource_type} · {snapshot.resource_key}
                      {snapshot.created_at ? ` · ${snapshot.created_at}` : ""}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={busy || !canRollback}
                    title={
                      canRollback
                        ? "Restore this snapshot on the connection"
                        : "This snapshot is not reversible"
                    }
                    onClick={() => onRollback(snapshot.id)}
                    data-testid={`projects-rollback-${snapshot.id}`}
                  >
                    Roll back
                  </Button>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
      <p className="text-xs text-muted">
        Full journal:{" "}
        <Link href={journalHref(connectionId)} className="text-accent hover:underline">
          Change journal
        </Link>
      </p>
    </section>
  );
}
