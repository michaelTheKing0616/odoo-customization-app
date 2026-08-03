"use client";

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
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Tabs } from "@/components/ui/Tabs";
import { Card, PageHeader } from "@/components/ui/layout-primitives";

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
    const list = tab === "csv" ? csvPreview?.assignments ?? [] : liveResult?.assignments ?? [];
    return changedOnly ? list.filter((r) => r.changed) : list;
  }, [tab, csvPreview, liveResult, changedOnly]);

  const previewColumns: DataTableColumn<IdGeneratorAssignmentOut>[] = [
    {
      id: "row",
      header: "Row",
      accessor: (r) => <span className="font-mono">{String(r.row_id)}</span>,
    },
    { id: "name", header: "Name", accessor: (r) => r.name },
    {
      id: "old",
      header: "Old",
      accessor: (r) => <span className="font-mono">{r.existing_code || "—"}</span>,
    },
    {
      id: "new",
      header: "New",
      accessor: (r) => <span className="font-mono">{r.new_code || "—"}</span>,
    },
  ];

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
    <div className="mx-auto max-w-5xl" data-testid="id-generator-page">
      <PageHeader
        title="ID Generator"
        description="PREFIX / INITIALS / NUMBER reference codes with semantic initials, collision disambiguation, and skip-if-present default."
      />
      <VersionAwarenessBanner capabilities={connection?.capabilities} />

      {error ? <ErrorNotice message={error} className="mt-4" /> : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4">
          {notice}
        </Callout>
      ) : null}

      <Tabs
        className="mt-6"
        value={tab}
        onValueChange={(v) => setTab(v as "csv" | "live")}
        items={[
          {
            value: "csv",
            label: "CSV",
            content: (
              <Card className="mt-4 space-y-3 p-4">
                <label className="block text-sm text-ink">
                  CSV / XLSX file
                  <input
                    type="file"
                    className="mt-1 block text-sm"
                    accept=".csv,.xlsx,.xlsm"
                    onChange={(e) => void onFileChange(e.target.files?.[0] ?? null)}
                  />
                </label>
                <Input
                  label="Name column"
                  value={nameColumn}
                  onChange={(e) => setNameColumn(e.target.value)}
                  className="font-mono text-sm"
                />
                <Input
                  label="Code column (optional)"
                  value={codeColumn}
                  onChange={(e) => setCodeColumn(e.target.value)}
                  className="font-mono text-sm"
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={busy}
                    loading={busy}
                    onClick={() => void previewCsv()}
                  >
                    Preview
                  </Button>
                  <Button
                    type="button"
                    variant="primary"
                    disabled={busy || !csvPreview}
                    onClick={() => void downloadCsv()}
                  >
                    Download updated CSV
                  </Button>
                </div>
              </Card>
            ),
          },
          {
            value: "live",
            label: "Live",
            content: (
              <Card className="mt-4 space-y-3 p-4">
                <Input
                  label="Model"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="font-mono text-sm"
                />
                <Input
                  label="Name field"
                  value={nameField}
                  onChange={(e) => setNameField(e.target.value)}
                  className="font-mono text-sm"
                />
                <Input
                  label="Code field"
                  value={codeField}
                  onChange={(e) => setCodeField(e.target.value)}
                  className="font-mono text-sm"
                />
                <Input
                  label="Record ids (optional)"
                  value={recordIds}
                  onChange={(e) => setRecordIds(e.target.value)}
                  placeholder="1, 2, 3"
                  className="font-mono text-sm"
                />
                <label className="flex items-center gap-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={createSequence}
                    onChange={(e) => setCreateSequence(e.target.checked)}
                  />
                  Create/update ir.sequence bridge after live apply
                </label>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={busy}
                    onClick={() => void runLive(true)}
                  >
                    Dry run
                  </Button>
                  <Button
                    type="button"
                    variant="primary"
                    disabled={busy}
                    onClick={() => void runLive(false)}
                  >
                    Apply codes
                  </Button>
                </div>
              </Card>
            ),
          },
        ]}
      />

      <Card className="mt-6 grid gap-3 p-4 sm:grid-cols-2">
        <Input
          label="Prefix"
          value={prefix}
          onChange={(e) => setPrefix(e.target.value.toUpperCase())}
          className="font-mono text-sm"
        />
        <Input
          label="Separator"
          value={separator}
          onChange={(e) => setSeparator(e.target.value)}
          className="font-mono text-sm"
        />
        <Input
          label="Number padding"
          type="number"
          value={String(padding)}
          onChange={(e) => setPadding(Number(e.target.value))}
        />
        <Input
          label="Initials length"
          type="number"
          value={String(initialsLength)}
          onChange={(e) => setInitialsLength(Number(e.target.value))}
        />
        <label className="flex items-center gap-2 text-sm text-ink sm:col-span-2">
          <input
            type="checkbox"
            checked={skipIfPresent}
            onChange={(e) => setSkipIfPresent(e.target.checked)}
          />
          Skip rows that already have a code (default ON)
        </label>
        <label className="flex items-center gap-2 text-sm text-ink sm:col-span-2">
          <input
            type="checkbox"
            checked={changedOnly}
            onChange={(e) => setChangedOnly(e.target.checked)}
          />
          Preview changed rows only
        </label>
      </Card>

      {previewRows.length > 0 ? (
        <Card className="mt-6 p-4">
          <h2 className="text-lg font-semibold text-ink">Preview</h2>
          <div className="mt-3">
            <DataTable
              columns={previewColumns}
              rows={previewRows}
              rowKey={(r) => String(r.row_id)}
            />
          </div>
        </Card>
      ) : null}

      <ConfirmDialogV2
        open={confirmOpen}
        riskLevel="danger"
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
    </div>
  );
}
