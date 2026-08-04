"use client";

import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";

export type PerRecordResult = {
  record_id: number;
  display_name?: string | null;
  ok: boolean;
  error?: string | null;
};

export type BulkRunResult = {
  run_id: string;
  operation: string;
  model: string;
  total: number;
  succeeded: number;
  failed: number;
  per_record: PerRecordResult[];
  dry_run?: boolean;
  message?: string;
  status?: string;
  pending_ids?: number[] | null;
  processed_count?: number | null;
  aborted?: boolean;
  can_continue?: boolean;
};

type BulkResultTableProps = {
  result: BulkRunResult;
  onRetryFailed?: () => void;
  onContinue?: () => void;
  onAbort?: () => void;
  continueBusy?: boolean;
  abortBusy?: boolean;
};

type Filter = "all" | "succeeded" | "failed";

export function BulkResultTable({
  result,
  onRetryFailed,
  onContinue,
  onAbort,
  continueBusy,
  abortBusy,
}: BulkResultTableProps) {
  const [filter, setFilter] = useState<Filter>("all");

  const rows = useMemo(() => {
    if (filter === "succeeded") return result.per_record.filter((r) => r.ok);
    if (filter === "failed") return result.per_record.filter((r) => !r.ok);
    return result.per_record;
  }, [filter, result.per_record]);

  const columns: DataTableColumn<PerRecordResult>[] = [
    {
      id: "id",
      header: "Record",
      accessor: (r) => (
        <span>
          {r.display_name ?? `#${r.record_id}`}
          <span className="ml-2 text-xs text-muted">#{r.record_id}</span>
        </span>
      ),
      sortValue: (r) => r.record_id,
    },
    {
      id: "status",
      header: "Status",
      accessor: (r) => (
        <Badge variant={r.ok ? "success" : "danger"}>{r.ok ? "Succeeded" : "Failed"}</Badge>
      ),
      sortValue: (r) => (r.ok ? 0 : 1),
    },
    {
      id: "error",
      header: "Detail",
      accessor: (r) => <span className="text-muted">{r.error ?? "—"}</span>,
    },
  ];

  return (
    <div className="space-y-3" data-testid="bulk-result-table">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Badge variant="info">{result.operation}</Badge>
        <span className="text-muted">
          {result.succeeded}/{result.total} succeeded
          {result.failed > 0 ? ` · ${result.failed} failed` : ""}
          {result.dry_run ? " · dry run" : ""}
          {result.status === "sample_paused" ? " · sample paused" : ""}
          {result.aborted ? " · aborted" : ""}
        </span>
        <div className="ml-auto flex gap-2">
          {result.can_continue && onContinue ? (
            <Button
              variant="primary"
              size="sm"
              type="button"
              disabled={continueBusy}
              onClick={onContinue}
            >
              Continue remaining
            </Button>
          ) : null}
          {result.status === "sample_paused" && onAbort ? (
            <Button
              variant="secondary"
              size="sm"
              type="button"
              disabled={abortBusy}
              onClick={onAbort}
            >
              Abort
            </Button>
          ) : null}
          {(
            [
              { id: "all" as const, label: "All" },
              { id: "succeeded" as const, label: "Succeeded" },
              { id: "failed" as const, label: "Failed" },
            ] as const
          ).map((f) => (
            <Button
              key={f.id}
              variant={filter === f.id ? "secondary" : "ghost"}
              size="sm"
              type="button"
              onClick={() => setFilter(f.id)}
            >
              {f.label}
            </Button>
          ))}
          {onRetryFailed && result.failed > 0 ? (
            <Button variant="primary" size="sm" type="button" onClick={onRetryFailed}>
              Retry failed
            </Button>
          ) : null}
        </div>
      </div>
      {result.message ? <p className="text-sm text-muted">{result.message}</p> : null}
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => String(r.record_id)}
        emptyState={<p className="text-center text-muted">No records in this filter.</p>}
      />
    </div>
  );
}
