"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/layout-primitives";
import type { ApprovalEntry } from "@/lib/api";
import { entriesEmptyGuide, entryStatusVariant } from "@/lib/approvalScreen";
import { ApprovalsStateGuide } from "./ApprovalsStateGuide";

type ApprovalEntriesListProps = {
  entries: ApprovalEntry[];
  loading?: boolean;
  busy?: boolean;
  onRefresh: () => void;
  onResolve: (entryId: string, approve: boolean) => void;
};

export function ApprovalEntriesList({
  entries,
  loading,
  busy,
  onRefresh,
  onResolve,
}: ApprovalEntriesListProps) {
  return (
    <section className="ap-section" data-testid="approval-entries-section">
      <div className="ap-list-head">
        <h2 className="ap-list-title">Entries / audit</h2>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onRefresh}
          data-testid="approval-entries-refresh"
        >
          Refresh
        </Button>
      </div>
      {loading ? (
        <div className="mt-3 space-y-2" data-testid="approval-entries-loading">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : entries.length === 0 ? (
        <div className="mt-3">
          <ApprovalsStateGuide
            testId="approval-entries-empty"
            guide={entriesEmptyGuide()}
            actions={
              <Button type="button" variant="secondary" size="sm" onClick={onRefresh}>
                Refresh entries
              </Button>
            }
          />
        </div>
      ) : (
        <ul className="ap-list">
          {entries.map((entry) => (
            <li key={entry.id} data-testid={`approval-entry-row-${entry.id}`}>
              <div className="ap-list-row">
                <div className="min-w-0">
                  <p className="ap-list-name">
                    {entry.record_model} #{entry.record_id} · step {entry.step_order}
                  </p>
                  <p className="ap-list-meta" style={{ fontFamily: "inherit" }}>
                    {entry.message}
                  </p>
                  {entry.status === "pending" ? (
                    <div className="ap-list-actions">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={busy}
                        onClick={() => onResolve(entry.id, true)}
                        data-testid={`approval-entry-approve-${entry.id}`}
                      >
                        Approve
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={busy}
                        onClick={() => onResolve(entry.id, false)}
                        data-testid={`approval-entry-reject-${entry.id}`}
                      >
                        Reject
                      </Button>
                    </div>
                  ) : null}
                </div>
                <Badge variant={entryStatusVariant(entry.status)}>{entry.status}</Badge>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
