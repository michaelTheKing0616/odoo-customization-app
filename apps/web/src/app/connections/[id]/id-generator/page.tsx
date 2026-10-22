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
import { Input } from "@/components/ui/Input";
import { Tabs } from "@/components/ui/Tabs";
import { PageHeader, Skeleton } from "@/components/ui/layout-primitives";
import { IdGeneratorResultCounts } from "@/components/id-generator/IdGeneratorResultCounts";
import { IdGeneratorStageRail } from "@/components/id-generator/IdGeneratorStageRail";
import { IdGeneratorStateGuide } from "@/components/id-generator/IdGeneratorStateGuide";
import {
  APPLY_CTA,
  CONFIRM_PHRASE,
  DRY_RUN_CTA,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PREVIEW_CTA,
  PRIMARY_CTA,
  applyBlockedReason,
  downloadBlockedReason,
  emptyCellDisplay,
  emptyIdGenGuide,
  formatCodeExample,
  idGenErrorGuide,
  idGenHonestyGuide,
  idGenStepFromState,
  previewCountsGuide,
  sanitizeIdGenCopy,
  sequenceHonestyGuide,
  type IdGenErrorContext,
  type IdGenMode,
} from "@/lib/idGeneratorScreen";
import "@/components/id-generator/id-generator-operate.css";

export default function IdGeneratorPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [connection, setConnection] = useState<Connection | null>(null);
  const [tab, setTab] = useState<IdGenMode>("csv");
  const [busy, setBusy] = useState(false);
  const [errorContext, setErrorContext] = useState<IdGenErrorContext | null>(null);
  const [errorDetail, setErrorDetail] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows, setRows] = useState<Record<string, string>[]>([]);
  const [nameColumn, setNameColumn] = useState("name");
  const [codeColumn, setCodeColumn] = useState("code");
  const [changedOnly, setChangedOnly] = useState(true);
  const [csvPreview, setCsvPreview] = useState<IdGeneratorPreviewOut | null>(null);
  const [csvDownloaded, setCsvDownloaded] = useState(false);

  const [model, setModel] = useState("x_blk_wf_item");
  const [nameField, setNameField] = useState("x_name");
  const [codeField, setCodeField] = useState("x_ref_code");
  const [recordIds, setRecordIds] = useState("");
  const [liveResult, setLiveResult] = useState<IdGeneratorRunOut | null>(null);
  const [previewHydrated, setPreviewHydrated] = useState(true);
  const [previewAttempted, setPreviewAttempted] = useState(false);

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

  const sampleCode = useMemo(
    () => formatCodeExample({ prefix, separator, padding, initialsLength }),
    [prefix, separator, padding, initialsLength],
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
      accessor: (r) => <span className="font-mono">{emptyCellDisplay(r.existing_code)}</span>,
    },
    {
      id: "new",
      header: "New",
      accessor: (r) => <span className="font-mono">{emptyCellDisplay(r.new_code)}</span>,
    },
  ];

  const hasSource =
    tab === "csv" ? Boolean(file) : Boolean(model.trim() && nameField.trim() && codeField.trim());
  const hasPreview = tab === "csv" ? Boolean(csvPreview) : Boolean(liveResult);
  const delivered =
    tab === "csv" ? csvDownloaded : Boolean(liveResult && liveResult.dry_run === false);
  const step = idGenStepFromState({ mode: tab, hasSource, hasPreview, delivered });

  const downloadReason = downloadBlockedReason({
    mode: tab,
    hasCsvPreview: Boolean(csvPreview),
    busy,
  });
  const applyReason = applyBlockedReason({
    mode: tab,
    busy,
    hasDryRun: Boolean(liveResult?.dry_run || (liveResult && liveResult.dry_run === false)),
  });

  const honesty = idGenHonestyGuide();
  const sequenceGuide = sequenceHonestyGuide(createSequence);
  const errorGuide =
    errorContext && errorDetail !== null
      ? idGenErrorGuide(errorContext, errorDetail)
      : errorContext
        ? idGenErrorGuide(errorContext)
        : null;

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => {
        setErrorContext("load");
        setErrorDetail(err.message);
      });
  }, [connectionId]);

  function clearError() {
    setErrorContext(null);
    setErrorDetail(null);
  }

  async function previewCsv() {
    if (!file) {
      setErrorContext("csv_preview");
      setErrorDetail("Choose a CSV or XLSX file first.");
      return;
    }
    setPreviewHydrated(false);
    setBusy(true);
    clearError();
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
      setCsvDownloaded(false);
      if (res.headers) setHeaders(res.headers);
      setNotice(sanitizeIdGenCopy(res.message));
      setPreviewAttempted(true);
    } catch (err) {
      setErrorContext("csv_preview");
      setErrorDetail(err instanceof Error ? err.message : "CSV preview failed");
    } finally {
      setBusy(false);
      setPreviewHydrated(true);
    }
  }

  async function downloadCsv() {
    if (!headers.length || !rows.length || !csvPreview) {
      setErrorContext("csv_download");
      setErrorDetail("Preview CSV first so the download includes new codes.");
      return;
    }
    setBusy(true);
    clearError();
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
      setCsvDownloaded(true);
      setNotice("Downloaded updated CSV. No Odoo writes.");
    } catch (err) {
      setErrorContext("csv_download");
      setErrorDetail(err instanceof Error ? err.message : "CSV download failed");
    } finally {
      setBusy(false);
    }
  }

  async function onFileChange(f: File | null) {
    setFile(f);
    setCsvPreview(null);
    setCsvDownloaded(false);
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
    setPreviewHydrated(false);
    setBusy(true);
    clearError();
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
      setNotice(sanitizeIdGenCopy(res.message));
      setPreviewAttempted(true);
      setConfirmOpen(false);
      if (!dryRun && createSequence) {
        try {
          await api.idGeneratorCreateSequence(connectionId, { model, config });
          setNotice(
            `${sanitizeIdGenCopy(res.message)} Sequence bridge updated after Apply (separate write).`,
          );
        } catch (seqErr) {
          setErrorContext("sequence");
          setErrorDetail(seqErr instanceof Error ? seqErr.message : "Sequence bridge failed");
          setNotice(
            `${sanitizeIdGenCopy(res.message)} Codes applied; sequence bridge failed (see error).`,
          );
        }
      }
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmOpen(true);
        setErrorContext("live_apply");
        setErrorDetail(err.warning);
      } else {
        setErrorContext(dryRun ? "live_dry_run" : "live_apply");
        setErrorDetail(err instanceof Error ? err.message : "Live ID generator failed");
      }
    } finally {
      setBusy(false);
      setPreviewHydrated(true);
    }
  }

  const countsSource =
    tab === "csv"
      ? csvPreview
        ? {
            total: csvPreview.total,
            changed: csvPreview.changed,
            skipped: csvPreview.skipped,
            dryRun: true as boolean | undefined,
          }
        : null
      : liveResult
        ? {
            total: liveResult.total,
            changed: liveResult.changed,
            skipped: liveResult.skipped,
            succeeded: liveResult.succeeded,
            failed: liveResult.failed,
            dryRun: liveResult.dry_run,
          }
        : null;

  const countsGuide = countsSource
    ? previewCountsGuide({
        total: countsSource.total,
        changed: countsSource.changed,
        skipped: countsSource.skipped,
        dryRun: countsSource.dryRun,
        mode: tab,
      })
    : null;

  return (
    <div className="idgen-operate" data-testid="id-generator-page">
      <PageHeader title={PAGE_TITLE} description={PAGE_DESCRIPTION} />
      <p className="ig-lead">
        {PRIMARY_CTA} is the primary action. Live Apply stays behind test run and the risk phrase.
      </p>
      <div className="ig-sample-code" data-testid="id-generator-sample-code">
        <span data-label="Sample">Sample</span>
        <span>{sampleCode}</span>
      </div>

      <VersionAwarenessBanner capabilities={connection?.capabilities} />

      <IdGeneratorStateGuide
        testId="id-generator-honesty"
        tone="accent"
        guide={honesty}
      />

      <IdGeneratorStageRail step={step} />

      {errorGuide ? (
        <IdGeneratorStateGuide
          testId="id-generator-error"
          tone="danger"
          live
          guide={errorGuide}
          className="mt-4"
        />
      ) : null}
      {notice ? (
        <Callout variant="info" title="Notice" className="mt-4" testId="id-generator-notice">
          {notice}
        </Callout>
      ) : null}

      <Tabs
        className="ig-mode-tabs"
        value={tab}
        onValueChange={(v) => setTab(v as IdGenMode)}
        items={[
          {
            value: "csv",
            label: "CSV",
            content: (
              <section className="ig-panel" aria-labelledby="idgen-csv-title">
                <h2 id="idgen-csv-title" className="ig-panel-title">
                  Spreadsheet source
                </h2>
                <p className="ig-panel-sub">
                  Preview proposes codes in-browser via the API. Download writes a file only, never Odoo.
                </p>
                <label className="ig-file-label">
                  CSV / XLSX file
                  <input
                    type="file"
                    accept=".csv,.xlsx,.xlsm"
                    data-testid="id-generator-file"
                    onChange={(e) => void onFileChange(e.target.files?.[0] ?? null)}
                  />
                </label>
                <div className="ig-grid ig-grid-2 mt-3">
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
                </div>
                <div className="ig-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={busy || !file}
                    loading={busy && tab === "csv"}
                    onClick={() => void previewCsv()}
                    data-testid="id-generator-preview-csv"
                  >
                    {PREVIEW_CTA}
                  </Button>
                  <Button
                    type="button"
                    variant="primary"
                    disabled={Boolean(downloadReason)}
                    onClick={() => void downloadCsv()}
                    data-testid="id-generator-download"
                  >
                    {PRIMARY_CTA}
                  </Button>
                  {downloadReason ? (
                    <span className="ig-primary-reason" data-testid="id-generator-download-reason">
                      {downloadReason}
                    </span>
                  ) : null}
                </div>
              </section>
            ),
          },
          {
            value: "live",
            label: "Live",
            content: (
              <section className="ig-panel" aria-labelledby="idgen-live-title">
                <h2 id="idgen-live-title" className="ig-panel-title">
                  Live Odoo target
                </h2>
                <p className="ig-panel-sub">
                  Test run lists proposed codes with no writes. Apply needs the risk phrase. Sequence bridge is optional and separate.
                </p>
                <div className="ig-grid ig-grid-2">
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
                </div>
                <label className="ig-check mt-3">
                  <input
                    type="checkbox"
                    checked={createSequence}
                    onChange={(e) => setCreateSequence(e.target.checked)}
                    data-testid="id-generator-sequence-toggle"
                  />
                  <span>Also create or update ir.sequence after Apply (separate write)</span>
                </label>
                <IdGeneratorStateGuide
                  testId="id-generator-sequence-guide"
                  tone={createSequence ? "warning" : "neutral"}
                  guide={sequenceGuide}
                  className="mt-3"
                />
                <div className="ig-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={busy}
                    onClick={() => void runLive(true)}
                    data-testid="id-generator-dry-run"
                  >
                    {DRY_RUN_CTA}
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={Boolean(applyReason)}
                    onClick={() => void runLive(false)}
                    data-testid="id-generator-apply"
                  >
                    {APPLY_CTA}
                  </Button>
                  {applyReason ? (
                    <span className="ig-primary-reason" data-testid="id-generator-apply-reason">
                      {applyReason}
                    </span>
                  ) : (
                    <span className="ig-primary-reason" data-testid="id-generator-apply-hint">
                      {PRIMARY_CTA} stays on the CSV tab. Apply writes only after test run and the risk phrase.
                    </span>
                  )}
                </div>
              </section>
            ),
          },
        ]}
      />

      <section className="ig-panel" aria-labelledby="idgen-rules-title">
        <h2 id="idgen-rules-title" className="ig-panel-title">
          Code rules
        </h2>
        <p className="ig-panel-sub">
          Same rules feed CSV preview, live test run, Apply, and an optional sequence bridge.
        </p>
        <div className="ig-grid ig-grid-2">
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
        </div>
        <label className="ig-check mt-3">
          <input
            type="checkbox"
            checked={skipIfPresent}
            onChange={(e) => setSkipIfPresent(e.target.checked)}
          />
          <span>Skip rows that already have a code (default on)</span>
        </label>
        <label className="ig-check mt-2">
          <input
            type="checkbox"
            checked={changedOnly}
            onChange={(e) => setChangedOnly(e.target.checked)}
          />
          <span>Show changed rows only in the preview table</span>
        </label>
      </section>

      <section className="ig-panel" aria-labelledby="idgen-preview-title" data-testid="id-generator-preview-panel">
        <h2 id="idgen-preview-title" className="ig-panel-title">
          Preview
        </h2>
        <p className="ig-panel-sub">
          {tab === "csv"
            ? "CSV preview and download never write Odoo."
            : liveResult?.dry_run === false
              ? "Live Apply result (writes applied for changed rows)."
              : "Live test run lists proposed codes with no writes."}
        </p>

        {busy || !previewHydrated ? (
          <div className="ig-progress" aria-busy="true" data-testid="id-generator-preview-loading" role="status">
            Working on {tab === "csv" ? "CSV preview" : "live run"}…
            <div className="mt-2 w-full space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          </div>
        ) : null}

        {countsSource && countsGuide && previewHydrated && !busy ? (
          <>
            <IdGeneratorStateGuide
              testId="id-generator-counts-guide"
              tone={countsSource.dryRun === false ? "warning" : "accent"}
              guide={countsGuide}
            />
            <IdGeneratorResultCounts
              total={countsSource.total}
              changed={countsSource.changed}
              skipped={countsSource.skipped}
              succeeded={"succeeded" in countsSource ? countsSource.succeeded : undefined}
              failed={"failed" in countsSource ? countsSource.failed : undefined}
              dryRun={countsSource.dryRun !== false}
            />
          </>
        ) : null}

        {!busy && previewHydrated && previewRows.length === 0 ? (
          <div className="mt-3" data-testid="id-generator-preview-empty">
            <IdGeneratorStateGuide
              testId="id-generator-empty-guide"
              tone="accent"
              guide={
                previewAttempted
                  ? {
                      title: "No code changes in this preview",
                      why: "Every row was skipped or already matched the rules (skip-if-present or changed-only filter).",
                      next: "Widen the row filter, clear skip-if-present, or adjust prefix rules, then run preview again.",
                    }
                  : emptyIdGenGuide(tab)
              }
              actions={
                tab === "csv" ? (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={busy || !file}
                    onClick={() => void previewCsv()}
                  >
                    {PREVIEW_CTA}
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={busy}
                    onClick={() => void runLive(true)}
                  >
                    {DRY_RUN_CTA}
                  </Button>
                )
              }
            />
          </div>
        ) : null}

        {!busy && previewHydrated && previewRows.length > 0 ? (
          <div className="ig-preview-wrap mt-3">
            <DataTable
              columns={previewColumns}
              rows={previewRows}
              rowKey={(r) => String(r.row_id)}
            />
          </div>
        ) : null}
      </section>

      <ConfirmDialogV2
        open={confirmOpen}
        riskLevel="danger"
        phrase={CONFIRM_PHRASE}
        title="Confirm live ID assignment"
        warning={`Write generated codes on live ${model} records. Test run listed proposals only; this step writes.`}
        risks={[
          "Only empty code fields are updated when skip-if-present is enabled",
          "Existing valid codes are not renumbered by default",
          createSequence
            ? "ir.sequence bridge will also be created or updated after Apply"
            : "ir.sequence bridge stays unchanged unless you enable it",
        ]}
        busy={busy}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) => void runLive(false, phrase)}
      />
    </div>
  );
}
