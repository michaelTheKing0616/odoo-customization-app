"use client";

import { PageHistory } from "@/components/history/PageHistory";
import type { SnapshotRow } from "@/lib/api";

const TYPES = new Set(["access", "rule"]);

type AccessSnapshotsProps = {
  connectionId: string;
  snapshots: SnapshotRow[];
  busy?: boolean;
  onRollback: (snapshotId: string) => void;
};

/** A4: this page's slice of the one History (shared panel, shared Undo). */
export function AccessSnapshots(props: AccessSnapshotsProps) {
  return (
    <PageHistory
      connectionId={props.connectionId}
      snapshots={props.snapshots}
      busy={props.busy}
      onRollback={props.onRollback}
      types={TYPES}
      testId="access-snapshots"
      emptyText="Nothing changed here yet. Grants you add, edit or remove show up here with Undo."
    />
  );
}
