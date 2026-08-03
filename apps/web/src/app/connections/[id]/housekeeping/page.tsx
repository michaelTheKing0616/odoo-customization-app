"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  api,
  AttachmentRowOut,
  BulkRunOut,
  ConfirmationRequiredError,
  Connection,
  DuplicateScanOut,
  LargeOldScanOut,
  OrphanScanOut,
} from "@/lib/api";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";

const CONFIRM_PHRASE = "I understand the risks";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function AttachmentTable({
  rows,
  selected,
  onToggle,
}: {
  rows: AttachmentRowOut[];
  selected: Set<number>;
  onToggle: (id: number) => void;
}) {
  if (!rows.length) {
    return <p className="text-sm text-[var(--odoo-muted)]">No rows.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--odoo-border)] text-[var(--odoo-muted)]">
            <th className="py-2 pr-2">Pick</th>
            <th className="py-2 pr-2">Name</th>
            <th className="py-2 pr-2">Linked</th>
            <th className="py-2 pr-2">Size</th>
            <th className="py-2 pr-2">Notes</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-[var(--odoo-border)]/60">
              <td className="py-2 pr-2 align-top">
                <input
                  type="checkbox"
                  disabled={!row.cleanable}
                  checked={selected.has(row.id)}
                  onChange={() => onToggle(row.id)}
                />
              </td>
              <td className="py-2 pr-2 align-top">{row.name}</td>
              <td className="py-2 pr-2 align-top font-mono text-xs">
                {row.res_model ? `${row.res_model} #${row.res_id ?? "?"}` : "standalone"}
              </td>
              <td className="py-2 pr-2 align-top">{formatBytes(row.file_size)}</td>
              <td className="py-2 pr-2 align-top text-xs text-[var(--odoo-muted)]">
                {row.cleanable ? "cleanable" : row.exclusion_reason || "excluded"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function HousekeepingPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [orphanScan, setOrphanScan] = useState<OrphanScanOut | null>(null);
  const [dupScan, setDupScan] = useState<DuplicateScanOut | null>(null);
  const [largeScan, setLargeScan] = useState<LargeOldScanOut | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [cleanKind, setCleanKind] = useState<"orphan" | "duplicate" | "large_old" | "manual">(
    "manual",
  );
  const [result, setResult] = useState<BulkRunOut | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmKind, setConfirmKind] = useState<"clean" | "recompute">("clean");
  const [minBytes, setMinBytes] = useState(1_048_576);
  const [olderDays, setOlderDays] = useState(90);
  const [recomputeModel, setRecomputeModel] = useState("");
  const [recomputeField, setRecomputeField] = useState("");
  const [recomputeIds, setRecomputeIds] = useState("");
  const [recomputeResult, setRecomputeResult] = useState<BulkRunOut | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const conn = await api.getConnection(connectionId);
        if (!cancelled) setConnection(conn);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load connection");
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [connectionId]);

  function toggleSelected(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectIds(ids: number[]) {
    setSelected(new Set(ids));
  }

  async function scanOrphans() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.bulkAttachmentOrphanScan(connectionId);
      setOrphanScan(res);
      setNotice(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Orphan scan failed");
    } finally {
      setBusy(false);
    }
  }

  async function scanDuplicates() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.bulkAttachmentDuplicateScan(connectionId);
      setDupScan(res);
      setNotice(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Duplicate scan failed");
    } finally {
      setBusy(false);
    }
  }

  async function scanLargeOld() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.bulkAttachmentLargeOldScan(connectionId, {
        min_bytes: minBytes,
        older_than_days: olderDays,
      });
      setLargeScan(res);
      setNotice(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Large/old scan failed");
    } finally {
      setBusy(false);
    }
  }

  async function clean(dryRun: boolean, phrase?: string) {
    const ids = [...selected];
    if (!ids.length) {
      setError("Select cleanable attachment(s) first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.bulkAttachmentClean(connectionId, {
        attachment_ids: ids,
        dry_run: dryRun,
        kind: cleanKind,
        ...(dryRun ? {} : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setResult(res);
      setNotice(res.message);
      setConfirmOpen(false);
      if (!dryRun) setSelected(new Set());
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmKind("clean");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Clean failed");
      }
    } finally {
      setBusy(false);
    }
  }

  function parseIdList(raw: string, label: string): number[] {
    const parts = raw
      .split(/[,\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (!parts.length) throw new Error(`Enter at least one ${label} id.`);
    const ids = parts.map((p) => {
      const n = Number(p);
      if (!Number.isInteger(n) || n <= 0) throw new Error(`Invalid ${label} id: ${p}`);
      return n;
    });
    return ids;
  }

  async function runRecompute(dryRun: boolean, phrase?: string) {
    if (!recomputeModel.trim() || !recomputeField.trim()) {
      setError("Model and field are required for recompute.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.bulkRecompute(connectionId, {
        model: recomputeModel.trim(),
        field: recomputeField.trim(),
        ...(recomputeIds.trim() ? { ids: parseIdList(recomputeIds, "record") } : {}),
        dry_run: dryRun,
        ...(dryRun ? {} : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setRecomputeResult(res);
      setNotice(res.message);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmKind("recompute");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Recompute failed");
      }
    } finally {
      setBusy(false);
    }
  }

  function parseIdList(raw: string, label: string): number[] {
    const parts = raw
      .split(/[,\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (!parts.length) throw new Error(`Enter at least one ${label} id.`);
    const ids = parts.map((p) => {
      const n = Number(p);
      if (!Number.isInteger(n) || n <= 0) throw new Error(`Invalid ${label} id: ${p}`);
      return n;
    });
    return ids;
  }

  async function runRecompute(dryRun: boolean, phrase?: string) {
    if (!recomputeModel.trim() || !recomputeField.trim()) {
      setError("Model and field are required for recompute.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.bulkRecompute(connectionId, {
        model: recomputeModel.trim(),
        field: recomputeField.trim(),
        ...(recomputeIds.trim() ? { ids: parseIdList(recomputeIds, "record") } : {}),
        dry_run: dryRun,
        ...(dryRun ? {} : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setRecomputeResult(res);
      setNotice(res.message);
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmKind("recompute");
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Recompute failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="odoo-shell min-h-screen px-6 py-10">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap gap-3 text-sm">
          <Link
            href={`/connections/${connectionId}`}
            className="text-[var(--odoo-primary-light)] hover:underline"
          >
            ← Metadata
          </Link>
          <Link
            href={`/connections/${connectionId}/bulk-suite`}
            className="text-[var(--odoo-primary-light)] hover:underline"
          >
            Bulk Suite
          </Link>
          <Link
            href={`/connections/${connectionId}/cron-manager`}
            className="text-[var(--odoo-primary-light)] hover:underline"
          >
            Cron Manager
          </Link>
        </div>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[var(--odoo-sheet-fg)]">
          Attachment housekeeping
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--odoo-muted)]">
          Scan orphaned files, checksum duplicates, and large old attachments. Review findings
          first — deletion requires the confirm phrase and never targets standalone uploads or view
          assets.
        </p>
        <VersionAwarenessBanner capabilities={connection?.capabilities} />

        {error && (
          <p className="mt-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
            {error}
          </p>
        )}
        {notice && (
          <p className="mt-4 rounded border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-900">
            {notice}
          </p>
        )}

        <section className="odoo-sheet mt-6 space-y-3 p-4">
          <h2 className="text-lg font-semibold">Orphan scan</h2>
          <p className="text-sm text-[var(--odoo-muted)]">
            Attachments whose parent record no longer exists.
          </p>
          <button type="button" className="odoo-btn-secondary" disabled={busy} onClick={() => void scanOrphans()}>
            Scan orphans
          </button>
          {orphanScan && (
            <>
              <p className="text-sm">
                Reclaimable: {formatBytes(orphanScan.total_reclaimable_bytes)} ·{" "}
                {orphanScan.orphans.length} orphan(s)
              </p>
              <AttachmentTable
                rows={orphanScan.orphans}
                selected={selected}
                onToggle={toggleSelected}
              />
              <button
                type="button"
                className="text-sm underline"
                onClick={() => {
                  setCleanKind("orphan");
                  selectIds(orphanScan.orphans.filter((r) => r.cleanable).map((r) => r.id));
                }}
              >
                Select all orphans
              </button>
              {orphanScan.standalone.length > 0 && (
                <details className="text-sm">
                  <summary>{orphanScan.standalone.length} standalone (not cleanable)</summary>
                  <AttachmentTable
                    rows={orphanScan.standalone}
                    selected={selected}
                    onToggle={toggleSelected}
                  />
                </details>
              )}
            </>
          )}
        </section>

        <section className="odoo-sheet mt-6 space-y-3 p-4">
          <h2 className="text-lg font-semibold">Duplicate scan</h2>
          <p className="text-sm text-[var(--odoo-muted)]">
            Groups by checksum — keep-newest default; select duplicate losers to reclaim space.
          </p>
          <button type="button" className="odoo-btn-secondary" disabled={busy} onClick={() => void scanDuplicates()}>
            Scan duplicates
          </button>
          {dupScan && (
            <>
              <p className="text-sm">
                Reclaimable: {formatBytes(dupScan.total_reclaimable_bytes)} ·{" "}
                {dupScan.groups.length} group(s)
              </p>
              {dupScan.groups.map((g) => (
                <div key={g.checksum} className="rounded border border-[var(--odoo-border)] p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    <span className="font-mono text-xs">{g.checksum.slice(0, 12)}…</span>
                    <span>{formatBytes(g.reclaimable_bytes)} reclaimable</span>
                    <button
                      type="button"
                      className="text-xs underline"
                      onClick={() => {
                        setCleanKind("duplicate");
                        selectIds(g.duplicate_ids);
                      }}
                    >
                      Select duplicates (keep #{g.keep_id})
                    </button>
                  </div>
                  <AttachmentTable rows={g.members} selected={selected} onToggle={toggleSelected} />
                </div>
              ))}
            </>
          )}
        </section>

        <section className="odoo-sheet mt-6 space-y-3 p-4">
          <h2 className="text-lg font-semibold">Large / old scan</h2>
          <div className="flex flex-wrap gap-3">
            <label className="block text-sm">
              Min size (bytes)
              <input
                type="number"
                min={1}
                className="mt-1 block border border-[var(--odoo-border)] bg-white px-2 py-1.5"
                value={minBytes}
                onChange={(e) => setMinBytes(Number(e.target.value) || 1)}
              />
            </label>
            <label className="block text-sm">
              Older than (days)
              <input
                type="number"
                min={1}
                className="mt-1 block border border-[var(--odoo-border)] bg-white px-2 py-1.5"
                value={olderDays}
                onChange={(e) => setOlderDays(Number(e.target.value) || 1)}
              />
            </label>
          </div>
          <button type="button" className="odoo-btn-secondary" disabled={busy} onClick={() => void scanLargeOld()}>
            Scan large/old
          </button>
          {largeScan && (
            <>
              <p className="text-sm">
                Reclaimable: {formatBytes(largeScan.total_reclaimable_bytes)} ·{" "}
                {largeScan.attachments.filter((r) => r.cleanable).length} cleanable
              </p>
              <AttachmentTable
                rows={largeScan.attachments}
                selected={selected}
                onToggle={toggleSelected}
              />
              <button
                type="button"
                className="text-sm underline"
                onClick={() => {
                  setCleanKind("large_old");
                  selectIds(largeScan.attachments.filter((r) => r.cleanable).map((r) => r.id));
                }}
              >
                Select all cleanable
              </button>
            </>
          )}
        </section>

        <section className="odoo-sheet mt-6 space-y-3 p-4">
          <h2 className="text-lg font-semibold">Stored compute recompute</h2>
          <p className="text-sm text-[var(--odoo-muted)]">
            Refresh stored computed fields by touching dependencies with tracking disabled. Probe
            runs on up to three records first — if it fails, no writes are made and you get an
            honest hosting message.
          </p>
          <label className="block text-sm">
            Model
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
              value={recomputeModel}
              onChange={(e) => setRecomputeModel(e.target.value)}
              placeholder="x_blk_wf_item"
            />
          </label>
          <label className="block text-sm">
            Stored field
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
              value={recomputeField}
              onChange={(e) => setRecomputeField(e.target.value)}
              placeholder="x_title_len"
            />
          </label>
          <label className="block text-sm">
            Record ids (optional)
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
              value={recomputeIds}
              onChange={(e) => setRecomputeIds(e.target.value)}
              placeholder="1, 2, 3"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="odoo-btn-secondary"
              disabled={busy}
              onClick={() => void runRecompute(true)}
            >
              Dry run
            </button>
            <button
              type="button"
              className="odoo-btn-primary"
              disabled={busy}
              onClick={() => void runRecompute(false)}
            >
              Recompute
            </button>
          </div>
          {recomputeResult?.probe && (
            <div className="rounded border border-[var(--odoo-border)] p-3 text-sm">
              <p className="font-medium">
                Probe {recomputeResult.probe.ok ? "ok" : "failed"} ·{" "}
                {recomputeResult.probe.message}
              </p>
              {recomputeResult.probe.honesty_message && (
                <p className="mt-2 text-amber-900">{recomputeResult.probe.honesty_message}</p>
              )}
              {recomputeResult.dependencies && recomputeResult.dependencies.length > 0 && (
                <p className="mt-1 text-xs text-[var(--odoo-muted)]">
                  Depends on: {recomputeResult.dependencies.join(", ")}
                </p>
              )}
            </div>
          )}
        </section>

        <section className="odoo-sheet mt-6 space-y-3 p-4">
          <h2 className="text-lg font-semibold">Stored compute recompute</h2>
          <p className="text-sm text-[var(--odoo-muted)]">
            Refresh stored computed fields by touching dependencies with tracking disabled. Probe
            runs on up to three records first — if it fails, no writes are made and you get an
            honest hosting message.
          </p>
          <label className="block text-sm">
            Model
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
              value={recomputeModel}
              onChange={(e) => setRecomputeModel(e.target.value)}
              placeholder="x_blk_wf_item"
            />
          </label>
          <label className="block text-sm">
            Stored field
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
              value={recomputeField}
              onChange={(e) => setRecomputeField(e.target.value)}
              placeholder="x_title_len"
            />
          </label>
          <label className="block text-sm">
            Record ids (optional)
            <input
              className="mt-1 w-full border border-[var(--odoo-border)] bg-white px-2 py-1.5 font-mono text-sm"
              value={recomputeIds}
              onChange={(e) => setRecomputeIds(e.target.value)}
              placeholder="1, 2, 3"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="odoo-btn-secondary"
              disabled={busy}
              onClick={() => void runRecompute(true)}
            >
              Dry run
            </button>
            <button
              type="button"
              className="odoo-btn-primary"
              disabled={busy}
              onClick={() => void runRecompute(false)}
            >
              Recompute
            </button>
          </div>
          {recomputeResult?.probe && (
            <div className="rounded border border-[var(--odoo-border)] p-3 text-sm">
              <p className="font-medium">
                Probe {recomputeResult.probe.ok ? "ok" : "failed"} ·{" "}
                {recomputeResult.probe.message}
              </p>
              {recomputeResult.probe.honesty_message && (
                <p className="mt-2 text-amber-900">{recomputeResult.probe.honesty_message}</p>
              )}
              {recomputeResult.dependencies && recomputeResult.dependencies.length > 0 && (
                <p className="mt-1 text-xs text-[var(--odoo-muted)]">
                  Depends on: {recomputeResult.dependencies.join(", ")}
                </p>
              )}
            </div>
          )}
        </section>

        <section className="odoo-sheet mt-6 space-y-3 p-4">
          <h2 className="text-lg font-semibold">Clean selected ({selected.size})</h2>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="odoo-btn-secondary"
              disabled={busy || !selected.size}
              onClick={() => void clean(true)}
            >
              Dry run
            </button>
            <button
              type="button"
              className="odoo-btn-primary"
              disabled={busy || !selected.size}
              onClick={() => void clean(false)}
            >
              Delete selected
            </button>
          </div>
          {result && (
            <div className="text-sm">
              <p>{result.message}</p>
              {result.reclaimable_bytes != null && (
                <p className="text-xs text-[var(--odoo-muted)]">
                  {formatBytes(result.reclaimable_bytes)} · run_id={result.run_id}
                </p>
              )}
            </div>
          )}
        </section>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        phrase={CONFIRM_PHRASE}
        title={confirmKind === "recompute" ? "Confirm recompute" : "Delete attachments"}
        warning={
          confirmKind === "recompute"
            ? `Recompute stored field ${recomputeField || "?"} on ${recomputeModel || "model"} records.`
            : `Permanently delete ${selected.size} attachment(s)?`
        }
        risks={
          confirmKind === "recompute"
            ? [
                "Touches dependency fields with tracking disabled",
                "Aborts with zero writes when probe cannot confirm on this instance",
              ]
            : [
                "Permanent file deletion — not reversible via this app",
                "May include documents on business records including tier-1 models",
              ]
        }
        onConfirm={(phrase) =>
          void (confirmKind === "recompute" ? runRecompute(false, phrase) : clean(false, phrase))
        }
        onCancel={() => setConfirmOpen(false)}
        busy={busy}
      />
    </main>
  );
}
