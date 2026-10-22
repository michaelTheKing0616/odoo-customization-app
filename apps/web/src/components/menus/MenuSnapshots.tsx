"use client";

import { PageHistory } from "@/components/history/PageHistory";
import type { SnapshotRow } from "@/lib/api";

const TYPES = new Set(["menu", "action"]);

type MenuSnapshotsProps = {
  connectionId: string;
  snapshots: SnapshotRow[];
  busy?: boolean;
  onRollback: (snapshotId: string) => void;
};

/** A4: this page's slice of the one History (shared panel, shared Undo). */
export function MenuSnapshots(props: MenuSnapshotsProps) {
  return (
    <PageHistory
      connectionId={props.connectionId}
      snapshots={props.snapshots}
      busy={props.busy}
      onRollback={props.onRollback}
      types={TYPES}
      testId="menus-snapshots"
      rowTestId={(id) => `menus-snapshot-${id}`}
      emptyText="Nothing changed here yet. Menu saves show up here with Undo."
    />
  );
}
