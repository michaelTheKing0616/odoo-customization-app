"use client";

import { PageHistory } from "@/components/history/PageHistory";
import type { SnapshotRow } from "@/lib/api";

const TYPES = new Set(["field", "model"]);

type BuilderSnapshotsProps = {
  connectionId: string;
  snapshots: SnapshotRow[];
  busy?: boolean;
  onRollback: (snapshotId: string) => void;
};

/** A4: this page's slice of the one History (shared panel, shared Undo). */
export function BuilderSnapshots(props: BuilderSnapshotsProps) {
  return (
    <PageHistory
      connectionId={props.connectionId}
      snapshots={props.snapshots}
      busy={props.busy}
      onRollback={props.onRollback}
      types={TYPES}
      testId="builder-snapshots"
      emptyText="Nothing changed here yet. Field and model changes show up here with Undo."
    />
  );
}
