"use client";

import { PageHistory } from "@/components/history/PageHistory";
import type { SnapshotRow } from "@/lib/api";

const TYPES = new Set(["automation", "action", "server_action", "ir_cron"]);

type AutomationSnapshotsProps = {
  connectionId: string;
  snapshots: SnapshotRow[];
  busy?: boolean;
  onRollback: (snapshotId: string) => void;
};

/** A4: this page's slice of the one History (shared panel, shared Undo). */
export function AutomationSnapshots(props: AutomationSnapshotsProps) {
  return (
    <PageHistory
      connectionId={props.connectionId}
      snapshots={props.snapshots}
      busy={props.busy}
      onRollback={props.onRollback}
      types={TYPES}
      testId="automations-snapshots"
      emptyText="Nothing changed here yet. Rules you create or remove show up here with Undo. Undo restores the rule, not business data."
    />
  );
}
