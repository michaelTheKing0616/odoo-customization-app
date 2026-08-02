"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, Connection } from "@/lib/api";
import { ConfirmDialog } from "@/components/ConfirmDialog";
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

  useEffect(() => {
    const sel = reports.find((r) => r.id === selectedId);
    setArch(sel?.arch || "");
  }, [selectedId, reports]);

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

  return (
    <main className="odoo-shell min-h-screen px-6 py-10">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap gap-4 text-sm">
          <Link href={`/connections/${connectionId}`} className="text-[#c9a9c0] hover:underline">
            ← Metadata
          </Link>
          <Link
            href={`/connections/${connectionId}/menus`}
            className="text-[#8f7a88] hover:underline"
          >
            Menus
          </Link>
        </div>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[#faf6f9]">
          Report layout lite
        </h1>
        <p className="mt-1 text-sm text-[#8f7a88]">
          QWeb PDF reports + paper formats via <code>ir.actions.report</code>
        </p>
        <VersionAwarenessBanner
          capabilities={connection?.capabilities}
          caveat={reportsCaveat}
        />
        {mutateBlocked && (
          <p className="mt-2 text-sm text-[#e8d09f]">{mutateBlocked}</p>
        )}

        {error && <p className="mt-4 text-sm text-[#f0a8a0]">{error}</p>}
        {notice && <p className="mt-4 text-sm text-[#c9a9c0]">{notice}</p>}

        <form
          onSubmit={onCreate}
          className="mt-8 grid gap-3 border border-[#3d2a38] bg-[#0f1a16]/70 p-5 sm:grid-cols-2"
        >
          <h2 className="sm:col-span-2 font-[family-name:var(--font-display)] text-xl">
            New report
          </h2>
          <label className="text-sm">
            <span className="text-[#a8909e]">Name</span>
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
            />
          </label>
          <label className="text-sm">
            <span className="text-[#a8909e]">Model</span>
            <input
              required
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono"
            />
          </label>
          <label className="text-sm">
            <span className="text-[#a8909e]">Report key (QWeb)</span>
            <input
              required
              value={form.report_key}
              onChange={(e) => setForm({ ...form, report_key: e.target.value })}
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2 font-mono"
            />
          </label>
          <label className="text-sm">
            <span className="text-[#a8909e]">Paper format</span>
            <select
              value={form.paperformat_id}
              onChange={(e) => setForm({ ...form, paperformat_id: e.target.value })}
              className="mt-1 w-full border border-[#3d2a38] bg-[#0c090b] px-3 py-2"
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
            className="sm:col-span-2 h-10 bg-[#714B67] text-sm font-semibold text-white disabled:opacity-50"
          >
            Create report
          </button>
        </form>

        <div className="mt-8 grid gap-6 lg:grid-cols-[280px_1fr]">
          <ul className="max-h-96 space-y-1 overflow-auto border border-[#3d2a38] p-3 text-sm">
            {reports.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(r.id)}
                  className={`w-full px-2 py-1.5 text-left ${
                    selectedId === r.id ? "bg-[#3d2a38] text-[#faf6f9]" : "text-[#d4c4ce]"
                  }`}
                >
                  {r.name}
                  <span className="block font-mono text-[10px] text-[#8f7a88]">
                    {r.model} · {r.report_name}
                  </span>
                </button>
              </li>
            ))}
            {reports.length === 0 && (
              <li className="text-xs text-[#8f7a88]">No reports yet.</li>
            )}
          </ul>

          <div className="border border-[#3d2a38] bg-[#0f1a16]/70 p-4">
            <h2 className="text-sm font-semibold text-[#c9a9c0]">QWeb arch</h2>
            <textarea
              value={arch}
              onChange={(e) => setArch(e.target.value)}
              rows={16}
              disabled={!selectedId}
              className="mt-2 w-full border border-[#3d2a38] bg-[#0c090b] p-3 font-mono text-xs disabled:opacity-40"
            />
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
                className="h-9 bg-[#714B67] px-4 text-sm font-semibold text-white disabled:opacity-50"
              >
                Save arch
              </button>
              <button
                type="button"
                disabled={busy || !selectedId || !canAdvanced}
                title={advancedBlocked ?? undefined}
                onClick={() => setConfirmDelete(true)}
                className="h-9 border border-[#a85b4a] px-4 text-sm text-[#f0a8a0] disabled:opacity-50"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
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
    </main>
  );
}
