"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { RelativeTime } from "@/components/ui/craft";
import { api } from "@/lib/api";

/** A4: the single timeline of every write on this database, filterable by page and record type. */
export function HistoryTimeline({ connectionId }: { connectionId: string }) {
  const [page, setPage] = useState("");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["history", connectionId, page, q],
    queryFn: () => api.history(connectionId, { page, q }),
  });
  const undo = async (snapshotId: string, label: string) => {
    setBusy(snapshotId);
    setNote(null);
    try {
      await api.rollbackSnapshot(connectionId, snapshotId);
      setNote(`Undone: ${label}. The undo itself is in History too.`);
      await qc.invalidateQueries({ queryKey: ["history", connectionId] });
    } catch (e) {
      setNote(`Couldn\u2019t undo: ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  };
  const entries = query.data?.entries ?? [];
  return (
    <section className="mt-4 space-y-3" data-testid="history-timeline" aria-label="Everything that changed">
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="Page"
          value={page}
          onChange={(e) => setPage(e.target.value)}
          className="rounded border border-border bg-background px-2 py-1 text-sm"
          data-testid="history-filter-page"
        >
          <option value="">All pages</option>
          {(query.data?.pages ?? []).map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search changes or record types"
          className="min-w-[14rem] flex-1 rounded border border-border bg-background px-2 py-1 text-sm"
          data-testid="history-filter-q"
        />
      </div>
      {note ? (
        <p role="status" className="text-sm text-ink">
          {note}
        </p>
      ) : null}
      {query.isLoading ? <p className="text-sm text-muted">Reading History\u2026</p> : null}
      {!query.isLoading && entries.length === 0 ? (
        <p className="text-sm text-muted" data-testid="history-empty">
          Nothing has changed here yet. Every change Ingenium makes will show up here, with Undo where Odoo allows it.
        </p>
      ) : null}
      <ol className="stagger space-y-2">
        {entries.map((e) => (
          <li key={e.id} className="hairline flex flex-wrap items-center justify-between gap-3 rounded-md p-3" data-testid={`history-row-${e.id}`}>
            <div className="min-w-0">
              <p className="truncate text-sm text-ink">{e.label}</p>
              <p className="text-xs text-muted">
                {e.page}
                {e.record_type ? <> · <span className="font-mono">{e.record_type}</span></> : null}
                {e.at ? <> · <RelativeTime value={e.at} /></> : null}
              </p>
            </div>
            {e.undo ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                loading={busy === e.undo.snapshot_id}
                disabled={Boolean(busy)}
                onClick={() => undo(e.undo!.snapshot_id, e.label)}
              >
                {e.undo.partial ? "Undo what Odoo allows" : "Undo"}
              </Button>
            ) : (
              <span className="text-xs text-muted">Record only</span>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
