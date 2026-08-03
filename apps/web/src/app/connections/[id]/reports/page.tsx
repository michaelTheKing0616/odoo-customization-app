"use client";

import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, Connection } from "@/lib/api";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { ReportDesigner } from "@/components/reports/ReportDesigner";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import {
  advancedMutationAllowed,
  advancedMutationBlockedReason,
  connectionSupports,
  mutationAllowed,
  mutationBlockedReason,
} from "@/lib/capabilities";

const MENUS_REPORTS_CAVEAT =
  "Menus / QWeb reports are experimental on Odoo 16 — verify in Open-in-Odoo after create.";

const CONFIRM_PHRASE = "I understand the risks";

export default function ReportsPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [reports, setReports] = useState<
    Array<{
      id: number;
      name: string;
      model: string | null;
      report_name: string | null;
      paperformat_name: string | null;
      arch: string | null;
    }>
  >([]);
  const [papers, setPapers] = useState<Array<{ id: number; name: string }>>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [arch, setArch] = useState("");
  const [form, setForm] = useState({
    name: "Custom document",
    model: "res.partner",
    report_key: "custom.report_partner",
    paperformat_id: "" as string,
  });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [mergeRows, setMergeRows] = useState<
    Array<{ reportId: string; recordIds: string }>
  >([{ reportId: "", recordIds: "1" }]);
  const [renderProbe, setRenderProbe] = useState<string | null>(null);
  const [editorTab, setEditorTab] = useState<"visual" | "code">("visual");

  const refresh = useCallback(async () => {
    const [r, p] = await Promise.all([
      api.listReports(connectionId),
      api.listPaperformats(connectionId),
    ]);
    setReports(r);
    setPapers(p);
  }, [connectionId]);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => setError(err.message));
  }, [connectionId]);

  useEffect(() => {
    refresh().catch((err: Error) => setError(err.message));
  }, [refresh]);

  const reportsCaveat = useMemo(() => {
    if (
      mutationAllowed(connection) &&
      !connectionSupports(connection, "list_as_list_type")
    ) {
      return MENUS_REPORTS_CAVEAT;
    }
    return null;
  }, [connection]);

  const canMutate = mutationAllowed(connection);
  const mutateBlocked = mutationBlockedReason(connection);
  const canAdvanced = advancedMutationAllowed(connection);
  const advancedBlocked = advancedMutationBlockedReason(connection);

  const selectedReport = reports.find((r) => r.id === selectedId) ?? null;

  useEffect(() => {
    setArch(selectedReport?.arch || "");
  }, [selectedReport]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api.createReport(connectionId, {
        name: form.name,
        model: form.model,
        report_key: form.report_key,
        paperformat_id: form.paperformat_id ? Number(form.paperformat_id) : null,
      });
      setNotice(`Created report #${created.id}`);
      await refresh();
      setSelectedId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function downloadMergedPdf() {
    const items = mergeRows
      .map((row) => ({
        report_id: Number(row.reportId),
        record_ids: row.recordIds
          .split(/[\s,]+/)
          .map((s) => s.trim())
          .filter(Boolean)
          .map((s) => Number(s))
          .filter((n) => Number.isFinite(n) && n > 0),
      }))
      .filter((item) => item.report_id > 0 && item.record_ids.length > 0);
    if (items.length < 1) {
      setError("Pick at least one report and record id(s) for combined print.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const { blob, totalPages, renderPath } = await api.mergePrintReports(connectionId, {
        items,
        filename: "combined-report.pdf",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "combined-report.pdf";
      a.click();
      URL.revokeObjectURL(url);
      setNotice(
        `Downloaded merged PDF (${totalPages ?? "?"} pages via ${renderPath ?? "render"})`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Combined print failed");
    } finally {
      setBusy(false);
    }
  }

  async function probeRenderPath() {
    setBusy(true);
    setError(null);
    try {
      const probe = await api.reportRenderProbe(connectionId);
      setRenderProbe(`${probe.primary_path} — ${probe.message}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Render probe failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl" data-testid="reports-page">
      <PageHeader
        title="Report layout lite"
        description="QWeb PDF reports + paper formats via ir.actions.report"
      />
      <VersionAwarenessBanner
        capabilities={connection?.capabilities}
        caveat={reportsCaveat}
      />
      {mutateBlocked ? (
        <Callout variant="warning" title="Mutations blocked" className="mt-4">
          {mutateBlocked}
        </Callout>
      ) : null}

      {error ? <ErrorNotice message={error} className="mt-4" /> : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {notice}
        </Callout>
      ) : null}

      <Card className="mt-8 p-5">
        <form onSubmit={onCreate} className="grid gap-3 sm:grid-cols-2">
          <h2 className="sm:col-span-2 text-xl font-semibold text-ink">New report</h2>
          <label className="text-sm">
            <span className="text-muted">Name</span>
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="mt-1 w-full rounded-md border border-border-subtle bg-surface-raised px-3 py-2"
            />
          </label>
          <label className="text-sm">
            <span className="text-muted">Model</span>
            <input
              required
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
              className="mt-1 w-full rounded-md border border-border-subtle bg-surface-raised px-3 py-2 font-mono"
            />
          </label>
          <label className="text-sm">
            <span className="text-muted">Report key (QWeb)</span>
            <input
              required
              value={form.report_key}
              onChange={(e) => setForm({ ...form, report_key: e.target.value })}
              className="mt-1 w-full rounded-md border border-border-subtle bg-surface-raised px-3 py-2 font-mono"
            />
          </label>
          <label className="text-sm">
            <span className="text-muted">Paper format</span>
            <select
              value={form.paperformat_id}
              onChange={(e) => setForm({ ...form, paperformat_id: e.target.value })}
              className="mt-1 w-full rounded-md border border-border-subtle bg-surface-raised px-3 py-2"
            >
              <option value="">— default —</option>
              {papers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={busy || !canMutate}
            title={mutateBlocked ?? undefined}
            className="sm:col-span-2 h-10 bg-accent text-sm font-semibold text-white disabled:opacity-50"
          >
            Create report
          </button>
        </form>
      </Card>

        <div className="mt-8 grid gap-6 lg:grid-cols-[280px_1fr]">
          <ul className="max-h-96 space-y-1 overflow-auto border border-border-subtle p-3 text-sm">
            {reports.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(r.id)}
                  className={`w-full px-2 py-1.5 text-left ${
                    selectedId === r.id ? "bg-surface-raised text-ink" : "text-muted"
                  }`}
                >
                  {r.name}
                  <span className="block font-mono text-[10px] text-muted">
                    {r.model} · {r.report_name}
                  </span>
                </button>
              </li>
            ))}
            {reports.length === 0 && (
              <li className="text-xs text-muted">No reports yet.</li>
            )}
          </ul>

          <div className="rounded-md border border-border-subtle bg-surface p-4">
            <div className="flex gap-2 border-b border-border-subtle pb-2">
              <button
                type="button"
                onClick={() => setEditorTab("visual")}
                className={`px-3 py-1 text-sm ${
                  editorTab === "visual"
                    ? "bg-accent text-white"
                    : "text-muted hover:underline"
                }`}
              >
                Visual designer
              </button>
              <button
                type="button"
                onClick={() => setEditorTab("code")}
                className={`px-3 py-1 text-sm ${
                  editorTab === "code"
                    ? "bg-accent text-white"
                    : "text-muted hover:underline"
                }`}
              >
                QWeb code
              </button>
            </div>
            {editorTab === "visual" ? (
              <div className="mt-4">
                {!selectedId ? (
                  <p className="text-sm text-muted">
                    Create or select a report to open the visual designer.
                  </p>
                ) : (
                  <ReportDesigner
                    connectionId={connectionId}
                    model={selectedReport?.model || form.model}
                    reportKey={selectedReport?.report_name || form.report_key}
                    reportName={selectedReport?.name || form.name}
                    reportId={selectedId}
                    paperLabel={selectedReport?.paperformat_name || "A4"}
                    onArchChange={setArch}
                    onNotice={setNotice}
                    onError={setError}
                  />
                )}
              </div>
            ) : (
              <>
                <h2 className="mt-4 text-sm font-semibold text-muted">QWeb arch</h2>
                <textarea
                  value={arch}
                  onChange={(e) => setArch(e.target.value)}
                  rows={16}
                  disabled={!selectedId}
                  className="mt-2 w-full rounded-md border border-border-subtle bg-surface-raised p-3 font-mono text-xs disabled:opacity-40"
                />
              </>
            )}
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                disabled={busy || !selectedId || !canMutate}
                title={mutateBlocked ?? undefined}
                onClick={async () => {
                  if (!selectedId) return;
                  setBusy(true);
                  try {
                    await api.updateReport(connectionId, selectedId, { arch });
                    setNotice(`Saved arch for #${selectedId}`);
                    await refresh();
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Save failed");
                  } finally {
                    setBusy(false);
                  }
                }}
                className="h-9 bg-accent px-4 text-sm font-semibold text-white disabled:opacity-50"
              >
                Save arch
              </button>
              <button
                type="button"
                disabled={busy || !selectedId || !canAdvanced}
                title={advancedBlocked ?? undefined}
                onClick={() => setConfirmDelete(true)}
                className="h-9 border border-danger px-4 text-sm text-danger disabled:opacity-50"
              >
                Delete
              </button>
            </div>
          </div>
        </div>

        <section className="mt-8 rounded-md border border-border-subtle bg-surface p-4">
          <h2 className="font-[family-name:var(--font-display)] text-xl text-ink">
            Combined print
          </h2>
          <p className="mt-1 text-sm text-muted">
            Render different QWeb PDF reports server-side and merge into one download — uses
            authenticated HTTP <code>/report/pdf</code> when RPC render is unavailable.
          </p>
          <div className="mt-4 space-y-3">
            {mergeRows.map((row, idx) => (
              <div key={idx} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                <label className="text-sm">
                  <span className="text-muted">Report</span>
                  <select
                    className="mt-1 w-full rounded-md border border-border-subtle bg-surface-raised px-2 py-1.5"
                    value={row.reportId}
                    onChange={(e) => {
                      const next = [...mergeRows];
                      next[idx] = { ...next[idx], reportId: e.target.value };
                      setMergeRows(next);
                    }}
                  >
                    <option value="">— pick —</option>
                    {reports.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} (#{r.id})
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm">
                  <span className="text-muted">Record ids</span>
                  <input
                    className="mt-1 w-full rounded-md border border-border-subtle bg-surface-raised px-2 py-1.5 font-mono"
                    value={row.recordIds}
                    onChange={(e) => {
                      const next = [...mergeRows];
                      next[idx] = { ...next[idx], recordIds: e.target.value };
                      setMergeRows(next);
                    }}
                    placeholder="1"
                  />
                </label>
                <button
                  type="button"
                  className="self-end border border-border-subtle px-3 py-1.5 text-sm text-danger"
                  disabled={mergeRows.length <= 1}
                  onClick={() => setMergeRows(mergeRows.filter((_, i) => i !== idx))}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              className="h-9 border border-border-subtle px-3 text-sm"
              onClick={() => setMergeRows([...mergeRows, { reportId: "", recordIds: "" }])}
            >
              Add report
            </button>
            <button
              type="button"
              className="h-9 border border-border-subtle px-3 text-sm"
              disabled={busy}
              onClick={() => void probeRenderPath()}
            >
              Probe render path
            </button>
            <button
              type="button"
              className="h-9 bg-accent px-4 text-sm font-semibold text-white disabled:opacity-50"
              disabled={busy}
              onClick={() => void downloadMergedPdf()}
            >
              Download merged PDF
            </button>
          </div>
          {renderProbe && (
            <p className="mt-3 text-xs text-muted">{renderProbe}</p>
          )}
        </section>

      <ConfirmDialogV2
        open={confirmDelete}
        riskLevel="danger"
        title="Delete report"
        warning="Removes the print action from this model."
        risks={["Users lose Print menu entry", "QWeb view may remain orphaned"]}
        phrase={CONFIRM_PHRASE}
        busy={busy}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={async (phrase) => {
          if (!selectedId) return;
          setBusy(true);
          try {
            await api.deleteReport(connectionId, selectedId, {
              confirm_advanced: true,
              confirm_phrase: phrase,
            });
            setConfirmDelete(false);
            setSelectedId(null);
            setNotice("Report deleted");
            await refresh();
          } catch (err) {
            setError(err instanceof Error ? err.message : "Delete failed");
          } finally {
            setBusy(false);
          }
        }}
      />
    </div>
  );
}
