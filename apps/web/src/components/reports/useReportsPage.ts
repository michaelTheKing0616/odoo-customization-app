"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, Connection } from "@/lib/api";
import type { MergeRow } from "@/components/reports/ReportsCombinedPrint";
import type { ReportsCreateFormValues } from "@/components/reports/ReportsCreateForm";
import type { ReportListRow } from "@/components/reports/ReportsListPanel";
import { refuseUnsafeQwebArch } from "@/components/reports/reportUnsafeGate";
import type { ReportInheritOp } from "@/components/reports/reportInheritSlots";
import { formatQwebRenderErrorDisplay } from "@/components/reports/reportRenderError";
import {
  advancedMutationAllowed,
  advancedMutationBlockedReason,
  connectionSupports,
  mutationAllowed,
  mutationBlockedReason,
} from "@/lib/capabilities";

const MENUS_REPORTS_CAVEAT =
  "Menus / QWeb reports are experimental on Odoo 16 — verify in Open-in-Odoo after create.";

export function useReportsPage(connectionId: string) {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [reports, setReports] = useState<ReportListRow[]>([]);
  const [papers, setPapers] = useState<Array<{ id: number; name: string }>>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [arch, setArch] = useState("");
  const [form, setForm] = useState<ReportsCreateFormValues>({
    name: "Custom document",
    model: "res.partner",
    report_key: "custom.report_partner",
    paperformat_id: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [mergeRows, setMergeRows] = useState<MergeRow[]>([
    { reportId: "", recordIds: "1" },
  ]);
  const [renderProbe, setRenderProbe] = useState<string | null>(null);
  const [editorTab, setEditorTab] = useState<"visual" | "code">("visual");
  const [listHydrated, setListHydrated] = useState(false);
  const [lastInheritOp, setLastInheritOp] = useState<ReportInheritOp | null>(null);

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
    setListHydrated(false);
    refresh()
      .catch((err: Error) => setError(err.message))
      .finally(() => setListHydrated(true));
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
      const spec = {
        name: form.name,
        model: form.model,
        report_key: form.report_key,
        mode: "primary" as const,
        use_external_layout: true,
        blocks: [
          { id: "h1", type: "heading", text: form.name || "Document", level: 1 },
          { id: "f1", type: "field", field: "display_name" },
        ],
      };
      const created = await api.createReport(connectionId, {
        name: form.name,
        model: form.model,
        report_key: form.report_key,
        paperformat_id: form.paperformat_id ? Number(form.paperformat_id) : null,
        spec,
      });
      setNotice(`Created printout #${created.id} (report.action.create on ${form.model})`);
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

  async function persistArch(nextArch: string, op: ReportInheritOp | null) {
    if (!selectedId) return;
    const unsafeErr = refuseUnsafeQwebArch(nextArch);
    if (unsafeErr) {
      setError(unsafeErr);
      throw new Error(unsafeErr);
    }
    setBusy(true);
    setError(null);
    try {
      await api.updateReport(connectionId, selectedId, {
        arch: nextArch,
        ...(op ? { inherit_op: op } : {}),
      });
      setLastInheritOp(op);
      setNotice(
        op
          ? `Saved report.inherit with one anchor (${op.params.xpath})`
          : `Saved arch for #${selectedId}`,
      );
      await refresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Save failed";
      setError(formatQwebRenderErrorDisplay(msg));
      throw err instanceof Error ? err : new Error(msg);
    } finally {
      setBusy(false);
    }
  }

  async function onDeleteConfirm(phrase: string) {
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
  }

  return {
    connection,
    reports,
    papers,
    selectedId,
    setSelectedId,
    arch,
    setArch,
    form,
    setForm,
    error,
    notice,
    setNotice,
    setError,
    busy,
    confirmDelete,
    setConfirmDelete,
    mergeRows,
    setMergeRows,
    renderProbe,
    editorTab,
    setEditorTab,
    listHydrated,
    lastInheritOp,
    setLastInheritOp,
    reportsCaveat,
    canMutate,
    mutateBlocked,
    canAdvanced,
    advancedBlocked,
    selectedReport,
    onCreate,
    downloadMergedPdf,
    probeRenderPath,
    persistArch,
    onDeleteConfirm,
    formatError: formatQwebRenderErrorDisplay,
  };
}
