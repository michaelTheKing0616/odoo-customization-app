"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  api,
  ConfirmationRequiredError,
  Connection,
  IdGeneratorAssignmentOut,
  IdGeneratorPreviewOut,
  IdGeneratorRunOut,
} from "@/lib/api";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";

const CONFIRM_PHRASE = "I understand the risks";

export default function IdGeneratorPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [tab, setTab] = useState<"csv" | "live">("csv");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows, setRows] = useState<Record<string, string>[]>([]);
  const [nameColumn, setNameColumn] = useState("name");
  const [codeColumn, setCodeColumn] = useState("code");
  const [changedOnly, setChangedOnly] = useState(true);
  const [csvPreview, setCsvPreview] = useState<IdGeneratorPreviewOut | null>(null);

  const [model, setModel] = useState("x_blk_wf_item");
  const [nameField, setNameField] = useState("x_name");
  const [codeField, setCodeField] = useState("x_ref_code");
  const [recordIds, setRecordIds] = useState("");
  const [liveResult, setLiveResult] = useState<IdGeneratorRunOut | null>(null);

  const [prefix, setPrefix] = useState("INV");
  const [separator, setSeparator] = useState("-");
  const [padding, setPadding] = useState(4);
  const [initialsLength, setInitialsLength] = useState(3);
  const [skipIfPresent, setSkipIfPresent] = useState(true);
  const [createSequence, setCreateSequence] = useState(false);

  const config = useMemo(
    () => ({
      prefix,
      separator,
      padding,
      initials_length: initialsLength,
      skip_if_present: skipIfPresent,
    }),
    [prefix, separator, padding, initialsLength, skipIfPresent],
  );

  const previewRows: IdGeneratorAssignmentOut[] = useMemo(() => {
    const rows = tab === "csv" ? csvPreview?.assignments ?? [] : liveResult?.assignments ?? [];
    return changedOnly ? rows.filter((r) => r.changed) : rows;
  }, [tab, csvPreview, liveResult, changedOnly]);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => setError(err.message));
  }, [connectionId]);

  async function previewCsv() {
    if (!file) {
      setError("Choose a CSV or XLSX file first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.idGeneratorCsvPreview(connectionId, file, {
        name_column: nameColumn,
        code_column: codeColumn || undefined,
        prefix,
        separator,
        padding,
        initials_length: initialsLength,
        skip_if_present: skipIfPresent,
        changed_only: changedOnly,
      });
      setCsvPreview(res);
      if (res.headers) setHeaders(res.headers);
      setNotice(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "CSV preview failed");
    } finally {
      setBusy(false);
    }
  }

  async function downloadCsv() {
    if (!headers.length || !rows.length || !csvPreview) {
      setError("Preview CSV first (upload file with stored rows in session).");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const blob = await api.idGeneratorCsvDownload(connectionId, {
        headers,
        rows,
        assignments: csvPreview.assignments,
        code_column: codeColumn || "code",
        changed_only: changedOnly,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "id-generator-updated.csv";
      a.click();
      URL.revokeObjectURL(url);
      setNotice("Downloaded updated CSV.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "CSV download failed");
    } finally {
      setBusy(false);
    }
  }

  async function onFileChange(f: File | null) {
    setFile(f);
    setCsvPreview(null);
    if (!f) return;
    try {
      const parsed = await api.idGeneratorCsvPreview(connectionId, f, {
        name_column: nameColumn,
        code_column: codeColumn || undefined,
        prefix,
        separator,
        padding,
        initials_length: initialsLength,
        skip_if_present: skipIfPresent,
        changed_only: false,
      });
      if (parsed.headers) setHeaders(parsed.headers);
      // Re-parse full rows via data import helper endpoint pattern
      const fdPreview = await api.dataImportPreview(connectionId, f, undefined);
      setRows(fdPreview.sample_rows);
      if (fdPreview.headers.length) {
        setHeaders(fdPreview.headers);
        if (fdPreview.headers.includes("name")) setNameColumn("name");
        if (fdPreview.headers.includes("code")) setCodeColumn("code");
      }
    } catch {
      /* preview on pick is best-effort */
    }
  }

  function parseRecordIds(): number[] | undefined {
    const ids = recordIds
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .map((s) => Number(s))
      .filter((n) => Number.isFinite(n) && n > 0);
    return ids.length ? ids : undefined;
  }

  async function runLive(dryRun: boolean, phrase?: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.idGeneratorLive(connectionId, {
        model,
        name_field: nameField,
        code_field: codeField,
        config,
        ids: parseRecordIds(),
        dry_run: dryRun,
        ...(dryRun ? {} : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setLiveResult(res);
      setNotice(res.message);
      setConfirmOpen(false);
      if (!dryRun && createSequence) {
        await api.idGeneratorCreateSequence(connectionId, { model, config });
        setNotice(`${res.message} · ir.sequence bridge updated.`);
      }
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmOpen(true);
        setError(err.warning);
      } else {
        setError(err instanceof Error ? err.message : "Live ID generator failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="odoo-shell min-h-screen px-6 py-10">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap gap-3 text-sm">
          <Link href={`/connections/${connectionId}`} className="text-[var(--odoo-primary-light)] hover:underline">
            ← Metadata
          </Link>
          <Link href={`/connections/${connectionId}/import`} className="text-[var(--odoo-primary-light)] hover:underline">
            Bulk import
          </Link>
        </div>
        <h1 className="mt-4 font-[family-name:var(--font-display)] text-3xl text-[var(--odoo-sheet-fg)]">
          ID Generator
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--odoo-muted)]">
          PREFIX / INITIALS / NUMBER reference codes with semantic initials, collision disambiguation,
          and skip-if-present default — only changed rows are written.
        </p>
        <VersionAwarenessBanner capabilities={connection?.capabilities} />

        <div className="mt-6 flex gap-2 text-sm">
          <button
            type="button"
            className={tab === "csv" ? "odoo-btn-primary" : "odoo-btn-secondary"}
            onClick={() => setTab("csv")}
          >
            CSV tab
          </button>
          <button
            type="button"
            className={tab === "live" ? "odoo-btn-primary" : "odoo-btn-secondary"}
            onClick={() => setTab("live")}
          >
            Live tab
          </button>
        </div>

        <section className="odoo-sheet mt-4 grid gap-3 p-4 sm:grid-cols-2">
          <label className="text-sm">
            Prefix
            <input className="mt-1 w-full border px-2 py-1.5 font-mono" value={prefix} onChange={(e) => setPrefix(e.target.value.toUpperCase())} />
          </label>
          <label className="text-sm">
            Separator
            <input className="mt-1 w-full border px-2 py-1.5 font-mono" value={separator} onChange={(e) => setSeparator(e.target.value)} />
          </label>
          <label className="text-sm">
            Number padding
            <input type="number" className="mt-1 w-full border px-2 py-1.5" value={padding} onChange={(e) => setPadding(Number(e.target.value))} />
          </label>
          <label className="text-sm">
            Initials length
            <input type="number" className="mt-1 w-full border px-2 py-1.5" value={initialsLength} onChange={(e) => setInitialsLength(Number(e.target.value))} />
          </label>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input type="checkbox" checked={skipIfPresent} onChange={(e) => setSkipIfPresent(e.target.checked)} />
            Skip rows that already have a code (default ON)
          </label>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input type="checkbox" checked={changedOnly} onChange={(e) => setChangedOnly(e.target.checked)} />
            Preview changed rows only
          </label>
        </section>

        {tab === "csv" ? (
          <section className="odoo-sheet mt-4 space-y-3 p-4">
            <label className="block text-sm">
              CSV / XLSX file
              <input type="file" className="mt-1 block" accept=".csv,.xlsx,.xlsm" onChange={(e) => void onFileChange(e.target.files?.[0] ?? null)} />
            </label>
            <label className="block text-sm">
              Name column
              <input className="mt-1 w-full border px-2 py-1.5 font-mono" value={nameColumn} onChange={(e) => setNameColumn(e.target.value)} />
            </label>
            <label className="block text-sm">
              Code column (optional)
              <input className="mt-1 w-full border px-2 py-1.5 font-mono" value={codeColumn} onChange={(e) => setCodeColumn(e.target.value)} />
            </label>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="odoo-btn-secondary" disabled={busy} onClick={() => void previewCsv()}>
                Preview
              </button>
              <button type="button" className="odoo-btn-primary" disabled={busy || !csvPreview} onClick={() => void downloadCsv()}>
                Download updated CSV
              </button>
            </div>
          </section>
        ) : (
          <section className="odoo-sheet mt-4 space-y-3 p-4">
            <label className="block text-sm">
              Model
              <input className="mt-1 w-full border px-2 py-1.5 font-mono" value={model} onChange={(e) => setModel(e.target.value)} />
            </label>
            <label className="block text-sm">
              Name field
              <input className="mt-1 w-full border px-2 py-1.5 font-mono" value={nameField} onChange={(e) => setNameField(e.target.value)} />
            </label>
            <label className="block text-sm">
              Code field
              <input className="mt-1 w-full border px-2 py-1.5 font-mono" value={codeField} onChange={(e) => setCodeField(e.target.value)} />
            </label>
            <label className="block text-sm">
              Record ids (optional)
              <input className="mt-1 w-full border px-2 py-1.5 font-mono" value={recordIds} onChange={(e) => setRecordIds(e.target.value)} placeholder="1, 2, 3" />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={createSequence} onChange={(e) => setCreateSequence(e.target.checked)} />
              Create/update ir.sequence bridge after live apply
            </label>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="odoo-btn-secondary" disabled={busy} onClick={() => void runLive(true)}>
                Dry run
              </button>
              <button type="button" className="odoo-btn-primary" disabled={busy} onClick={() => void runLive(false)}>
                Apply codes
              </button>
            </div>
          </section>
        )}

        {error && <p className="mt-4 text-sm text-[var(--odoo-danger)]">{error}</p>}
        {notice && !error && <p className="mt-4 text-sm text-[var(--odoo-success)]">{notice}</p>}

        {previewRows.length > 0 && (
          <section className="odoo-sheet mt-6 overflow-x-auto p-4">
            <h2 className="text-lg font-semibold">Preview</h2>
            <table className="mt-3 w-full text-left text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-1 pr-2">Row</th>
                  <th className="py-1 pr-2">Name</th>
                  <th className="py-1 pr-2">Old</th>
                  <th className="py-1">New</th>
                </tr>
              </thead>
              <tbody>
                {previewRows.map((row) => (
                  <tr key={String(row.row_id)} className="border-b/50">
                    <td className="py-1 pr-2 font-mono">{String(row.row_id)}</td>
                    <td className="py-1 pr-2">{row.name}</td>
                    <td className="py-1 pr-2 font-mono">{row.existing_code || "—"}</td>
                    <td className="py-1 font-mono">{row.new_code || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        phrase={CONFIRM_PHRASE}
        title="Confirm live ID assignment"
        warning={`Write generated codes on live ${model} records.`}
        risks={[
          "Only empty code fields are updated when skip-if-present is enabled",
          "Existing valid codes are not renumbered by default",
        ]}
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) => void runLive(false, phrase)}
      />
    </main>
  );
}
