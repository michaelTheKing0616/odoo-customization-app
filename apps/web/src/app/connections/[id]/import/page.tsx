"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  api,
  ConfirmationRequiredError,
  Connection,
  DataImportCommitOut,
  ImageImportCommitOut,
  ImageImportPreviewOut,
} from "@/lib/api";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { VersionAwarenessBanner } from "@/components/VersionAwarenessBanner";
import { ImportErrorNotice } from "@/components/import/ImportErrorNotice";
import { ImportResultCounts } from "@/components/import/ImportResultCounts";
import { ImportStageRail } from "@/components/import/ImportStageRail";
import { ImportStateGuide } from "@/components/import/ImportStateGuide";
import { SeedPackPicker } from "@/components/import/SeedPackPicker";
import { OperateStudioChrome } from "@/components/operate-studio/OperateStudioChrome";
import {
  CONFIRM_PHRASE,
  DRY_RUN_CTA,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PARSE_CTA,
  PRIMARY_CTA,
  commitBlockedReason,
  countStripFromResult,
  dryRunBlockedReason,
  emptyImportGuide,
  importHonestyGuide,
  importSessionBadge,
  importSessionHint,
  importStepFromState,
  mappingEmptyGuide,
  partialFailureGuide,
  sanitizeImportCopy,
  unmappedColumns,
  type ImportErrorContext,
} from "@/lib/importScreen";
import "@/components/import/import-operate.css";

type BusyKind = null | "preview" | "dry_run" | "commit" | "image_preview" | "image_commit" | "template";

export default function DataImportPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const connectionId = params.id;
  const showGallery = searchParams.get("gallery") === "1";

  const [connection, setConnection] = useState<Connection | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [model, setModel] = useState("res.partner");
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows, setRows] = useState<Record<string, string>[]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<"create" | "upsert">("create");
  const [matchFields, setMatchFields] = useState("email");
  const [busy, setBusy] = useState<BusyKind>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorContext, setErrorContext] = useState<ImportErrorContext>("load");
  const [notice, setNotice] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<DataImportCommitOut | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [imgManifest, setImgManifest] = useState<File | null>(null);
  const [imgZip, setImgZip] = useState<File | null>(null);
  const [imgPreview, setImgPreview] = useState<ImageImportPreviewOut | null>(null);
  const [imgMatchField, setImgMatchField] = useState("x_name");
  const [imgField, setImgField] = useState("");
  const [imgResult, setImgResult] = useState<ImageImportCommitOut | null>(null);
  const [imgConfirmOpen, setImgConfirmOpen] = useState(false);

  useEffect(() => {
    api
      .getConnection(connectionId)
      .then(setConnection)
      .catch((err: Error) => {
        setErrorContext("load");
        setError(err.message);
      });
  }, [connectionId]);

  const sample = useMemo(() => rows.slice(0, 5), [rows]);
  const importStep = importStepFromState({ rowCount: rows.length, lastResult });
  const gaps = useMemo(() => unmappedColumns(mapping, headers), [mapping, headers]);
  const commitReason = commitBlockedReason({
    rowCount: rows.length,
    busy: busy !== null,
    headers,
    mapping,
  });
  const dryRunReason = dryRunBlockedReason({
    rowCount: rows.length,
    busy: busy !== null,
    headers,
    mapping,
  });
  const countStrip = lastResult ? countStripFromResult(lastResult) : null;
  const failureGuide = countStrip ? partialFailureGuide(countStrip) : null;
  const imgStrip = imgResult ? countStripFromResult(imgResult) : null;

  async function onPreview() {
    if (!file) {
      setErrorContext("preview");
      setError("Choose a CSV or XLSX file first");
      return;
    }
    setBusy("preview");
    setError(null);
    setNotice(null);
    try {
      const preview = await api.dataImportPreview(connectionId, file, model);
      setHeaders(preview.headers);
      setRows(preview.sample_rows);
      setMapping(preview.suggested_mapping);
      if (preview.suggested_model) setModel(preview.suggested_model);
      setNotice(
        sanitizeImportCopy(
          `Parsed ${preview.row_count} row(s). Review mapping, then ${DRY_RUN_CTA}.`,
        ),
      );
      setLastResult(null);
    } catch (err) {
      setErrorContext("preview");
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setBusy(null);
    }
  }

  async function runCommit(dryRun: boolean, phrase?: string) {
    if (!rows.length) {
      setErrorContext(dryRun ? "dry_run" : "commit");
      setError("Parse a file first");
      return;
    }
    setBusy(dryRun ? "dry_run" : "commit");
    setError(null);
    try {
      const res = await api.dataImportCommit(connectionId, {
        model,
        mapping,
        mode,
        match_fields:
          mode === "upsert"
            ? matchFields
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean)
            : [],
        dry_run: dryRun,
        rows,
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setLastResult(res);
      setNotice(sanitizeImportCopy(res.message));
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmOpen(true);
        setError(null);
      } else {
        setErrorContext(dryRun ? "dry_run" : "commit");
        setError(err instanceof Error ? err.message : "Commit failed");
      }
    } finally {
      setBusy(null);
    }
  }

  async function downloadTemplate() {
    setBusy("template");
    setError(null);
    try {
      const t = await api.dataImportTemplate(connectionId, model);
      const blob = new Blob([t.csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = t.filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setErrorContext("template");
      setError(err instanceof Error ? err.message : "Could not download template");
    } finally {
      setBusy(null);
    }
  }

  async function downloadUsersTemplate() {
    setBusy("template");
    setError(null);
    try {
      const t = await api.usersCsvTemplate(connectionId);
      const blob = new Blob([t.csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = t.filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setErrorContext("template");
      setError(err instanceof Error ? err.message : "Could not download users.csv");
    } finally {
      setBusy(null);
    }
  }

  async function onImagePreview() {
    if (!imgManifest || !imgZip) {
      setErrorContext("image_preview");
      setError("Choose manifest CSV and images ZIP");
      return;
    }
    setBusy("image_preview");
    setError(null);
    setNotice(null);
    try {
      const preview = await api.imageImportPreview(connectionId, imgManifest, imgZip);
      setImgPreview(preview);
      setImgMatchField(preview.match_field);
      setImgField(preview.image_field);
      setImgResult(null);
      setNotice(
        sanitizeImportCopy(
          `Image manifest: ${preview.row_count} row(s). ${preview.warnings.join(" ")}`.trim(),
        ),
      );
    } catch (err) {
      setErrorContext("image_preview");
      setError(err instanceof Error ? err.message : "Image preview failed");
    } finally {
      setBusy(null);
    }
  }

  async function runImageCommit(dryRun: boolean, phrase?: string) {
    if (!imgManifest || !imgZip) {
      setErrorContext("image_commit");
      setError("Choose manifest CSV and images ZIP");
      return;
    }
    setBusy(dryRun ? "image_preview" : "image_commit");
    setError(null);
    try {
      const res = await api.imageImportCommit(connectionId, {
        model,
        manifest: imgManifest,
        imagesZip: imgZip,
        match_field: imgMatchField,
        image_field: imgField || undefined,
        dry_run: dryRun,
        ...(dryRun
          ? {}
          : { confirm_advanced: true, confirm_phrase: phrase || CONFIRM_PHRASE }),
      });
      setImgResult(res);
      setNotice(sanitizeImportCopy(res.message));
      setImgConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setImgConfirmOpen(true);
        setError(null);
      } else {
        setErrorContext("image_commit");
        setError(err instanceof Error ? err.message : "Image import failed");
      }
    } finally {
      setBusy(null);
    }
  }

  function downloadErrorCsv() {
    if (!lastResult?.error_csv) return;
    const blob = new Blob([lastResult.error_csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "import_errors.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const isBusy = busy !== null;
  const progressLabel =
    busy === "preview"
      ? "Parsing file…"
      : busy === "dry_run"
        ? "Running dry-run…"
        : busy === "commit"
          ? "Committing rows…"
          : busy === "image_preview"
            ? "Previewing images…"
            : busy === "image_commit"
              ? "Committing images…"
              : busy === "template"
                ? "Preparing download…"
                : null;

  const honesty = lastResult ? null : importHonestyGuide();
  const sessionHint = importSessionHint({ lastResult });

  return (
    <>
    <OperateStudioChrome
      testIdPrefix="import"
      pageTestId="import-page"
      kicker={connection?.name ?? connectionId}
      title={PAGE_TITLE}
      subtitle={PAGE_DESCRIPTION}
      badge={importSessionBadge(importStep)}
      honesty={honesty}
      hint={sessionHint}
      sanitize={sanitizeImportCopy}
      rail={<ImportStageRail step={importStep} />}
      shellClassName="import-operate"
      className="p-4 sm:p-6"
    >
      <VersionAwarenessBanner capabilities={connection?.capabilities} />
{error ? (
        <ImportErrorNotice
          className="mt-4"
          message={error}
          context={errorContext}
          onDismiss={() => setError(null)}
        />
      ) : null}
      {notice && !error ? (
        <Callout variant="info" title="Status" className="mt-4" testId="import-notice">
          {notice}
        </Callout>
      ) : null}

      {progressLabel ? (
        <div className="im-progress" aria-busy="true" data-testid="import-progress" role="status">
          {progressLabel}
        </div>
      ) : null}

      {rows.length === 0 && !error ? (
        <ImportStateGuide
          density="brief"
          testId="import-empty-guide"
          guide={emptyImportGuide()}
        />
      ) : null}

      <section className="im-panel" data-testid="import-seed-panel" aria-labelledby="import-seed-title">
        <h2 id="import-seed-title" className="im-panel-title">
          Industry seed packs
        </h2>
        <p className="im-panel-sub">Optional starter CSVs for common models on this connection.</p>
        <div
          data-testid="import-seed-gallery"
          className={showGallery ? "rounded-md border border-accent/40 bg-accent/5 p-3" : undefined}
        >
          <SeedPackPicker
            connectionId={connectionId}
            onPick={(m, csv) => {
              setModel(m);
              const blob = new Blob([csv], { type: "text/csv" });
              const next = new File([blob], `${m.replace(/\./g, "_")}_seed.csv`, {
                type: "text/csv",
              });
              setFile(next);
              setNotice(sanitizeImportCopy(`Loaded seed for ${m}. Click ${PARSE_CTA} to preview.`));
            }}
          />
        </div>
      </section>

      <section className="im-panel" data-testid="import-upload-panel" aria-labelledby="import-upload-title">
        <h2 id="import-upload-title" className="im-panel-title">
          Upload and map
        </h2>
        <p className="im-panel-sub">
          Target an Odoo model, parse the sheet, map columns, test run the counts, then {PRIMARY_CTA}.
        </p>

        <Input
          label="Target model"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder="res.partner"
          className="font-mono"
        />

        <div className="im-toolbar mt-3">
          <Button type="button" variant="secondary" size="sm" disabled={isBusy} onClick={() => void downloadTemplate()}>
            Download template
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={isBusy}
            onClick={() => void downloadUsersTemplate()}
          >
            Download users.csv
          </Button>
          <label className="im-file-label">
            CSV or XLSX
            <input
              type="file"
              accept=".csv,.xlsx,.xlsm,.txt"
              data-testid="import-file-input"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <Button
            type="button"
            variant="secondary"
            disabled={isBusy || !file}
            loading={busy === "preview"}
            data-testid="import-parse-btn"
            onClick={() => void onPreview()}
          >
            {PARSE_CTA}
          </Button>
        </div>

        {headers.length > 0 ? (
          <>
            <div className="im-mode-row">
              <Select
                label="Mode"
                value={mode}
                onChange={(e) => setMode(e.target.value as "create" | "upsert")}
                options={[
                  { value: "create", label: "Create" },
                  { value: "upsert", label: "Upsert" },
                ]}
              />
              {mode === "upsert" ? (
                <Input
                  label="Match fields (comma)"
                  value={matchFields}
                  onChange={(e) => setMatchFields(e.target.value)}
                  className="font-mono"
                />
              ) : null}
            </div>

            {gaps.length === headers.length ? (
              <ImportStateGuide className="!mt-3" testId="import-mapping-guide" guide={mappingEmptyGuide()} />
            ) : null}

            <div className="im-map-wrap" data-testid="import-mapping-table">
              <table className="im-map-table">
                <thead>
                  <tr>
                    <th scope="col">CSV column</th>
                    <th scope="col">Odoo field</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {headers.map((h) => {
                    const gap = !(mapping[h] || "").trim();
                    return (
                      <tr key={h} data-gap={gap ? "true" : "false"}>
                        <td className="font-mono text-xs">{h}</td>
                        <td>
                          <input
                            aria-label={`Map ${h} to Odoo field`}
                            value={mapping[h] ?? ""}
                            onChange={(e) => setMapping((m) => ({ ...m, [h]: e.target.value }))}
                          />
                        </td>
                        <td>
                          {gap ? <span className="im-gap-chip">Unmapped</span> : <span className="text-xs text-muted">Ready</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <p className="mt-3 text-xs text-muted" data-testid="import-row-count">
              {rows.length} row(s) loaded. Sample (first 5):
            </p>
            <div className="im-sample" data-testid="import-sample-table">
              <table>
                <thead>
                  <tr>
                    {headers.map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sample.map((row, i) => (
                    <tr key={i}>
                      {headers.map((h) => (
                        <td key={h} title={row[h] ?? ""}>
                          {row[h] ?? ""}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="im-actions">
              <Button
                type="button"
                variant="secondary"
                disabled={isBusy || Boolean(dryRunReason)}
                loading={busy === "dry_run"}
                data-testid="import-dry-run-btn"
                aria-describedby={dryRunReason ? "import-dry-run-reason" : undefined}
                onClick={() => void runCommit(true)}
              >
                {DRY_RUN_CTA}
              </Button>
              <Button
                type="button"
                variant="primary"
                disabled={isBusy || Boolean(commitReason)}
                loading={busy === "commit"}
                data-testid="import-commit-btn"
                aria-describedby={commitReason ? "import-commit-reason" : undefined}
                onClick={() => setConfirmOpen(true)}
              >
                {PRIMARY_CTA}
              </Button>
              {commitReason ? (
                <p id="import-commit-reason" className="im-primary-reason" data-testid="import-commit-reason">
                  {commitReason}
                </p>
              ) : dryRunReason ? (
                <p id="import-dry-run-reason" className="im-primary-reason" data-testid="import-dry-run-reason">
                  {dryRunReason}
                </p>
              ) : (
                <p className="im-primary-reason">Test run first to see create, update, skip, and error counts.</p>
              )}
            </div>
          </>
        ) : null}

        {countStrip ? (
          <div className="mt-4" data-testid="import-result-block">
            <p className="text-sm font-medium text-ink">
              {countStrip.dryRun ? "Test run counts" : "Commit counts"}
            </p>
            <ImportResultCounts strip={countStrip} />
            {countStrip.message ? (
              <p className="mt-2 text-sm text-muted" data-testid="import-result-message">
                {sanitizeImportCopy(countStrip.message)}
              </p>
            ) : null}
            {failureGuide ? (
              <ImportStateGuide
                className="!mt-3"
                tone="warning"
                live
                testId="import-partial-guide"
                guide={failureGuide}
                actions={
                  countStrip.hasErrorCsv ? (
                    <Button type="button" variant="secondary" size="sm" onClick={downloadErrorCsv}>
                      Download error CSV
                    </Button>
                  ) : null
                }
              />
            ) : countStrip.hasErrorCsv ? (
              <div className="im-guide-actions mt-3">
                <Button type="button" variant="secondary" size="sm" onClick={downloadErrorCsv}>
                  Download error CSV
                </Button>
              </div>
            ) : null}
            {lastResult && lastResult.results.length > 0 ? (
              <div className="im-result-rows" data-testid="import-row-results">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">#</th>
                      <th scope="col">Action</th>
                      <th scope="col">Record</th>
                      <th scope="col">Ok</th>
                      <th scope="col">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lastResult.results.slice(0, 50).map((r) => (
                      <tr key={r.row_index} data-ok={r.ok ? "true" : "false"}>
                        <td>{r.row_index}</td>
                        <td className="font-mono">{r.action ?? ""}</td>
                        <td className="font-mono">{r.record_id ?? ""}</td>
                        <td>{r.ok ? "yes" : "no"}</td>
                        <td className="text-danger">{r.error ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      <details className="im-fold" data-testid="image-import-panel">
        <summary>Bulk image import</summary>
        <div className="im-fold-body">
          <p className="im-panel-sub">
            CSV manifest (<code>match,name,filename</code>) plus a ZIP of images writes base64 to an
            image or binary field. Images are downscaled server-side (max 1920px, 5MB guard).
          </p>
          <div className="im-toolbar">
            <label className="im-file-label">
              Manifest CSV
              <input
                type="file"
                accept=".csv,.txt"
                data-testid="import-image-manifest"
                onChange={(e) => setImgManifest(e.target.files?.[0] ?? null)}
              />
            </label>
            <label className="im-file-label">
              Images ZIP
              <input
                type="file"
                accept=".zip"
                data-testid="import-image-zip"
                onChange={(e) => setImgZip(e.target.files?.[0] ?? null)}
              />
            </label>
            <Button
              type="button"
              variant="secondary"
              disabled={isBusy || !imgManifest || !imgZip}
              onClick={() => void onImagePreview()}
            >
              Preview manifest
            </Button>
          </div>
          {imgPreview ? (
            <>
              <div className="im-mode-row">
                <Input
                  label="Match field"
                  value={imgMatchField}
                  onChange={(e) => setImgMatchField(e.target.value)}
                  className="font-mono"
                />
                <Input
                  label="Image field"
                  value={imgField}
                  onChange={(e) => setImgField(e.target.value)}
                  placeholder={imgPreview.image_field}
                  className="font-mono"
                />
              </div>
              <div className="im-sample" data-testid="import-image-sample">
                <table>
                  <thead>
                    <tr>
                      {Object.keys(imgPreview.sample_rows[0] ?? { match: "", filename: "" }).map((h) => (
                        <th key={h}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {imgPreview.sample_rows.slice(0, 5).map((row, i) => (
                      <tr key={i}>
                        {Object.keys(row).map((h) => (
                          <td key={h}>{row[h]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="im-actions">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={isBusy}
                  onClick={() => void runImageCommit(true)}
                >
                  Test run images
                </Button>
                <Button
                  type="button"
                  variant="primary"
                  disabled={isBusy}
                  data-testid="import-image-commit-btn"
                  onClick={() => setImgConfirmOpen(true)}
                >
                  Commit images
                </Button>
              </div>
            </>
          ) : null}
          {imgStrip ? (
            <div className="mt-4" data-testid="image-import-results">
              <ImportResultCounts strip={imgStrip} testId="import-image-counts" />
              <div className="im-result-rows">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">#</th>
                      <th scope="col">Match</th>
                      <th scope="col">File</th>
                      <th scope="col">Ok</th>
                      <th scope="col">Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {imgResult!.results.map((r) => (
                      <tr key={r.row_index} data-ok={r.ok ? "true" : "false"}>
                        <td>{r.row_index}</td>
                        <td className="font-mono">{r.match_value}</td>
                        <td className="font-mono">{r.filename}</td>
                        <td>{r.ok ? "yes" : "no"}</td>
                        <td className="text-danger">{r.error ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </div>
      </details>

    </OperateStudioChrome>

    <ConfirmDialogV2
        open={confirmOpen}
        riskLevel="danger"
        title="Commit bulk import"
        warning={`Write ${rows.length} row(s) to ${model} on this live Odoo connection.`}
        risks={[
          "Creates or updates business records",
          "Wrong Many2one mapping can link incorrect relations",
          "Partial success is not auto-rolled back",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy === "commit"}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) => void runCommit(false, phrase)}
      />
      <ConfirmDialogV2
        open={imgConfirmOpen}
        riskLevel="danger"
        title="Commit bulk image import"
        warning={`Write images to ${model} on this live Odoo connection.`}
        risks={[
          "Overwrites binary or image data on matched records",
          "Wrong match field can attach images to incorrect records",
          "Partial success is not auto-rolled back",
        ]}
        phrase={CONFIRM_PHRASE}
        busy={busy === "image_commit"}
        onCancel={() => setImgConfirmOpen(false)}
        onConfirm={(phrase) => void runImageCommit(false, phrase)}
      />
    </>
  );
}
