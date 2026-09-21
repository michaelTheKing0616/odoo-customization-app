"use client";

import { useCallback, useMemo, useState } from "react";
import {
  api,
  BatchOsJob,
  ConfirmationRequiredError,
} from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Card } from "@/components/ui/layout-primitives";

const CONFIRM_PHRASE = "I understand the risks";

const TARGETS = [
  "journal",
  "date",
  "ref",
  "label",
  "account",
  "debit",
  "credit",
  "partner",
  "analytic",
  "move_group",
] as const;

type Props = { connectionId: string };

export function JournalBatchPanel({ connectionId }: Props) {
  const [job, setJob] = useState<BatchOsJob | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [columnMap, setColumnMap] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [postAfter, setPostAfter] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const headers = job?.headers ?? [];

  const onUpload = useCallback(async () => {
    if (!file) {
      setError("Choose a CSV or XLSX file first");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const next = await api.batchOsJournalIntake(connectionId, file);
      setJob(next);
      setColumnMap(next.column_map || {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }, [connectionId, file]);

  const runMap = useCallback(async () => {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.batchOsJournalMap(connectionId, {
        job_id: job.job_id,
        column_map: columnMap,
      });
      setJob(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Map failed");
    } finally {
      setBusy(false);
    }
  }, [connectionId, job, columnMap]);

  const runDryRun = useCallback(async () => {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      await api.batchOsJournalMap(connectionId, {
        job_id: job.job_id,
        column_map: columnMap,
      });
      const next = await api.batchOsJournalDryRun(connectionId, {
        job_id: job.job_id,
      });
      setJob(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dry-run failed");
    } finally {
      setBusy(false);
    }
  }, [connectionId, job, columnMap]);

  const doApply = useCallback(
    async (confirmed: boolean) => {
      if (!job) return;
      setBusy(true);
      setError(null);
      try {
        const next = await api.batchOsJournalApply(connectionId, {
          job_id: job.job_id,
          post_after_create: postAfter,
          confirm_advanced: confirmed,
          confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
        });
        setJob(next);
        setConfirmOpen(false);
      } catch (err) {
        if (err instanceof ConfirmationRequiredError) {
          setConfirmOpen(true);
        } else {
          setError(err instanceof Error ? err.message : "Apply failed");
        }
      } finally {
        setBusy(false);
      }
    },
    [connectionId, job, postAfter],
  );

  const blocking = useMemo(
    () => (job?.errors || []).filter((e) => e.code === "blocking"),
    [job],
  );

  return (
    <div className="space-y-4" data-testid="journal-batch-panel">
      <Callout variant="info" title="Preview ≠ posted">
        Dry-run checks balance and resolves accounts via public RPC. Apply creates{" "}
        <strong>draft</strong> <code className="text-xs">account.move</code> rows.
        Optional post is L2 and needs confirm.
      </Callout>

      {error ? <ErrorNotice message={error} /> : null}

      <Card className="space-y-3 p-4">
        <p className="text-sm font-medium text-ink">1. Upload CSV / XLSX</p>
        <input
          type="file"
          accept=".csv,.xlsx,.xlsm,.txt"
          data-testid="journal-batch-file"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <Button
          type="button"
          size="sm"
          variant="primary"
          disabled={busy || !file}
          onClick={() => void onUpload()}
        >
          Intake
        </Button>
      </Card>

      {job ? (
        <>
          <Card className="space-y-3 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="info">{job.phase}</Badge>
              <Badge variant={job.risk === "L2" || job.risk === "L3" ? "danger" : "default"}>
                {job.risk}
              </Badge>
              <span className="text-xs text-muted">
                {job.filename} · {job.raw_row_count} rows · job {job.job_id.slice(0, 8)}
              </span>
            </div>
            <p className="text-sm text-muted">{job.message}</p>

            <p className="text-sm font-medium text-ink">2. Column map</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {headers.map((h) => (
                <label key={h} className="flex items-center gap-2 text-xs">
                  <span className="w-28 truncate font-mono text-ink" title={h}>
                    {h}
                  </span>
                  <select
                    className="flex-1 rounded border border-border-subtle bg-surface px-2 py-1"
                    value={columnMap[h] || ""}
                    onChange={(e) =>
                      setColumnMap((prev) => ({ ...prev, [h]: e.target.value }))
                    }
                  >
                    <option value="">— skip —</option>
                    {TARGETS.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => void runMap()}>
                Map
              </Button>
              <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => void runDryRun()}>
                Dry-run
              </Button>
            </div>
          </Card>

          {job.moves?.length ? (
            <Card className="space-y-2 p-4" data-testid="journal-batch-moves">
              <p className="text-sm font-medium text-ink">Moves preview</p>
              <ul className="space-y-2 text-xs">
                {job.moves.map((m) => (
                  <li
                    key={m.group_key}
                    className="rounded border border-border-subtle p-2 font-mono"
                  >
                    <span className={m.balanced ? "text-success" : "text-danger"}>
                      {m.balanced ? "balanced" : "UNBALANCED"}
                    </span>{" "}
                    · {m.date} · ref={m.ref} · lines={m.line_count} · Dr {m.total_debit} / Cr{" "}
                    {m.total_credit}
                    {m.move_id ? ` · move#${m.move_id}${m.posted ? " POSTED" : " draft"}` : ""}
                    {m.errors?.length ? (
                      <span className="block text-muted">{m.errors.join("; ")}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {blocking.length ? (
            <Callout variant="danger" title="Blocking errors">
              <ul className="list-disc pl-4 text-xs">
                {blocking.map((e, i) => (
                  <li key={`${e.row_index}-${i}`}>
                    row {e.row_index}
                    {e.field ? ` · ${e.field}` : ""}: {e.message}
                  </li>
                ))}
              </ul>
            </Callout>
          ) : null}

          <Card className="space-y-3 p-4">
            <p className="text-sm font-medium text-ink">3. Apply</p>
            <label className="flex items-center gap-2 text-sm text-muted">
              <input
                type="checkbox"
                checked={postAfter}
                onChange={(e) => setPostAfter(e.target.checked)}
              />
              Also post after create (L2)
            </label>
            <Button
              type="button"
              size="sm"
              variant="primary"
              disabled={busy || job.phase === "failed"}
              onClick={() => void doApply(false)}
            >
              Apply drafts
            </Button>
            {job.created_move_ids?.length ? (
              <p className="text-xs text-ink">
                Created: {job.created_move_ids.join(", ")}
                {job.posted_move_ids?.length
                  ? ` · Posted: ${job.posted_move_ids.join(", ")}`
                  : ""}
              </p>
            ) : null}
          </Card>
        </>
      ) : null}

      <ConfirmDialogV2
        open={confirmOpen}
        title="Confirm journal batch apply"
        warning="Journal batch apply writes to live Odoo Accounting"
        phrase={CONFIRM_PHRASE}
        riskLevel={postAfter ? "danger" : "standard"}
        risks={[
          "Writes account.move drafts to live Odoo",
          postAfter ? "Will post (L2)" : "Drafts only unless you checked post",
        ]}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void doApply(true)}
        busy={busy}
      />
    </div>
  );
}
