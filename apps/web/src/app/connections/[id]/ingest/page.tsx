"use client";

import { Term } from "@/components/ui/Term";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  api,
  ConfirmationRequiredError,
  IngestJobOut,
} from "@/lib/api";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { OperateStudioChrome } from "@/components/operate-studio/OperateStudioChrome";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import {
  Card,
  Skeleton,
} from "@/components/ui/layout-primitives";
import { DOC_TYPE_OPTIONS, docTypeLabel } from "@/components/ingest/docTypes";
import {
  IngestStepRail,
  resolveIngestStep,
} from "@/components/ingest/IngestStepRail";
import {
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  emptyIngestGuide,
  ingestHonestyGuide,
  ingestSessionBadge,
  ingestSessionHint,
  sanitizeIngestCopy,
} from "@/lib/ingestScreen";
import "@/components/ingest/ingest-operate.css";
import { IconImport } from "@/components/ui/icons";

const CONFIRM_PHRASE = "I understand the risks";

export default function UniversalIngestPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [files, setFiles] = useState<File[]>([]);
  const [job, setJob] = useState<IngestJobOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [visionMsg, setVisionMsg] = useState<string | null>(null);
  const [notifyMode, setNotifyMode] = useState<"batch_summary" | "individual">(
    "batch_summary",
  );
  const [allowCoaAsIs, setAllowCoaAsIs] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [overrideReason, setOverrideReason] = useState("");

  const [businessName, setBusinessName] = useState("");
  const [productLines, setProductLines] = useState("");
  const [contacts, setContacts] = useState("");
  const [expenseCats, setExpenseCats] = useState("");

  useEffect(() => {
    api.ingestVisionStatus(connectionId).then((s) => setVisionMsg(s.message)).catch(() => null);
    api
      .ingestGetPrefs(connectionId)
      .then((p) => {
        setNotifyMode(p.notify_mode);
        setAllowCoaAsIs(p.allow_coa_as_is_default);
      })
      .catch(() => null);
  }, [connectionId]);

  const gaps = job?.batch.plan?.gaps ?? job?.batch.gaps ?? [];
  const hasFinancial = Boolean(
    job?.batch.files.some((f) =>
      ["coa", "opening_trial_balance"].includes(f.doc_type),
    ),
  );
  const log = job?.batch.commit_log;
  const needsTypeConfirm = Boolean(
    job?.batch.files.some((f) => f.needs_user_confirm),
  );
  const overrideReasonTrimmed = overrideReason.trim();
  const canApplyOverrides = needsTypeConfirm && overrideReasonTrimmed.length >= 3;

  const currentStep = useMemo(
    () =>
      resolveIngestStep({
        hasJob: Boolean(job),
        needsTypeConfirm,
        hasDryRunLog: Boolean(log?.dry_run),
        hasCommitLog: Boolean(log && !log.dry_run),
      }),
    [job, log, needsTypeConfirm],
  );

  async function downloadUsersTemplate() {
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
      setError(
        err instanceof Error
          ? err.message
          : "Could not download the users.csv template. Check the connection, then try again.",
      );
    }
  }

  async function uploadAndPlan() {
    if (!files.length) {
      setError(
        "Select at least one CSV, XLSX, PDF, or image file. Why: ingest needs source rows to classify. Next: choose files, then Analyze and plan.",
      );
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await api.ingestCreateJob(connectionId, files);
      setJob(created);
      const o: Record<string, string> = {};
      for (const f of created.batch.files) o[f.id] = f.doc_type;
      setOverrides(o);
      setOverrideReason("");
      setNotice(
        "Files classified and ordered. Review types and gaps, then test run before commit.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function applyOverrides() {
    if (!job) return;
    if (!canApplyOverrides) {
      setError(
        "Add a short reason before changing document types. Why: overrides change the commit plan. Next: say why the auto type is wrong, then apply.",
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await api.ingestOverride(connectionId, job.id, {
        force_doc_types: overrides,
      });
      setJob(updated);
      setNotice(
        `Classification overridden (${overrideReasonTrimmed}). Plan rebuilt.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runInterview() {
    if (!businessName.trim()) {
      setError(
        "Enter a business name. Why: starter products and contacts need a company context. Next: name the business, then Build from interview.",
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await api.ingestCreateInterviewJob(connectionId, {
        business_name: businessName.trim(),
        product_type: "mixed",
        product_lines: productLines.split("\n").filter(Boolean),
        starter_contacts: contacts.split("\n").filter(Boolean),
        expense_categories: expenseCats.split("\n").filter(Boolean),
      });
      setJob(created);
      setNotice(
        "Interview batch planned. Same test run and commit path as file uploads.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runDryRun() {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.ingestDryRun(connectionId, job.id, {
        notify_mode: notifyMode,
        allow_coa_as_is: allowCoaAsIs,
      });
      setJob(updated);
      setNotice("Test run complete. No records were written to Odoo.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runCommit(confirmPhrase?: string) {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.ingestCommit(connectionId, job.id, {
        confirm_advanced: Boolean(confirmPhrase),
        confirm_phrase: confirmPhrase ?? null,
        notify_mode: notifyMode,
        allow_coa_as_is: allowCoaAsIs,
      });
      setJob(updated);
      setNotice("Commit finished. Writes were applied on the connected Odoo.");
      setConfirmOpen(false);
    } catch (err) {
      if (err instanceof ConfirmationRequiredError) {
        setConfirmOpen(true);
        setError(null);
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setBusy(false);
    }
  }

  const hasDryRunLog = Boolean(log?.dry_run);
  const hasCommitLog = Boolean(log && !log.dry_run);
  const honesty = hasCommitLog || hasDryRunLog ? null : ingestHonestyGuide();
  const sessionHint = ingestSessionHint({ hasCommitLog, hasDryRunLog });

  return (
    <OperateStudioChrome
      testIdPrefix="ingest"
      pageTestId="ingest-page"
      kicker={connectionId}
      title={PAGE_TITLE}
      subtitle={PAGE_DESCRIPTION}
      badge={ingestSessionBadge(currentStep)}
      honesty={honesty}
      hint={sessionHint}
      sanitize={sanitizeIngestCopy}
      rail={<IngestStepRail current={currentStep} />}
      shellClassName="ingest-operate"
      className="p-4 sm:p-6"
    >
      <div className="ig-actions" style={{ justifyContent: "flex-end" }}>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => void downloadUsersTemplate()}
        >
          Download users.csv template
        </Button>
      </div>

      {visionMsg ? (
        <Callout variant="info" title="Vision OCR">
          {visionMsg}
        </Callout>
      ) : null}

      {error ? (
        <ErrorNotice
          title="Ingest could not continue"
          message={error}
          onRetry={job ? () => void runDryRun() : undefined}
        />
      ) : null}
      {notice ? (
        <Callout variant="info" title="Ready" testId="ingest-notice">
          {notice}
        </Callout>
      ) : null}

      {busy && !job ? (
        <Card className="space-y-3 p-4" role="status" aria-live="polite">
          <p className="sr-only">Analyzing files.</p>
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-9 w-36" />
        </Card>
      ) : null}

      <Card className="space-y-4 p-4" data-testid="ingest-upload-card">
        <div>
          <h2 className="text-sm font-semibold text-ink">Upload files</h2>
          <p className="mt-1 text-xs text-muted">
            CSV, XLSX, PDF, or images. Analyze builds the classification and
            commit order.
          </p>
        </div>
        <label
          className="flex cursor-pointer flex-col items-start gap-3 rounded-md border border-dashed border-border-subtle bg-surface-muted/40 px-4 py-6 transition-colors duration-[80ms] hover:border-accent/40 hover:bg-accent/5 focus-within:ring-2 focus-within:ring-accent focus-within:ring-offset-2"
          data-testid="ingest-dropzone"
        >
          <span className="inline-flex items-center gap-2 text-sm font-medium text-ink">
            <IconImport className="size-4 text-muted" aria-hidden />
            Choose files
          </span>
          <input
            type="file"
            multiple
            accept=".csv,.xlsx,.xlsm,.pdf,.png,.jpg,.jpeg,.webp,text/csv,application/pdf,image/*"
            data-testid="ingest-file-input"
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
            className="block w-full text-sm text-muted file:mr-3 file:rounded-md file:border-0 file:bg-surface-raised file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-ink"
          />
          {files.length > 0 ? (
            <ul className="w-full space-y-1 text-xs text-muted">
              {files.map((f) => (
                <li key={`${f.name}-${f.size}`} className="font-mono tabular-nums">
                  {f.name}{" "}
                  <span className="text-muted">
                    ({Math.max(1, Math.round(f.size / 1024))} KB)
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-muted">No files selected yet.</p>
          )}
        </label>
        <Button
          type="button"
          variant="secondary"
          data-testid="ingest-analyze-btn"
          onClick={() => void uploadAndPlan()}
          disabled={busy || !files.length}
          loading={busy && !job}
        >
          Analyze and plan
        </Button>
      </Card>

      <Card className="space-y-4 p-4" data-testid="ingest-interview-card">
        <div>
          <h2 className="text-sm font-semibold text-ink">
            Or build starter data from an interview
          </h2>
          <p className="mt-1 text-xs text-muted">
            Same test run and commit path as uploads. Expense categories guide
            product categories, not the chart of accounts.
          </p>
        </div>
        <Input
          label="Business name"
          placeholder="e.g. North Bridge Trading"
          value={businessName}
          onChange={(e) => setBusinessName(e.target.value)}
          data-testid="ingest-business-name"
        />
        <Textarea
          label="Products"
          hint="One per line: Name | SKU | Price"
          rows={2}
          value={productLines}
          onChange={(e) => setProductLines(e.target.value)}
          placeholder="Name | SKU | Price"
          data-testid="ingest-product-lines"
        />
        <Textarea
          label="Contacts"
          hint="One per line: Name | Email | Phone"
          rows={2}
          value={contacts}
          onChange={(e) => setContacts(e.target.value)}
          placeholder="Name | Email | Phone"
          data-testid="ingest-contacts"
        />
        <Textarea
          label="Expense categories"
          hint="Guidance for product.category, not CoA accounts"
          rows={2}
          value={expenseCats}
          onChange={(e) => setExpenseCats(e.target.value)}
          placeholder="Office supplies"
          data-testid="ingest-expense-cats"
        />
        <Button
          type="button"
          variant="secondary"
          data-testid="ingest-interview-btn"
          onClick={() => void runInterview()}
          disabled={busy}
        >
          Build from interview
        </Button>
      </Card>

      

      {job ? (
        <>
          <Card className="space-y-3 p-4" data-testid="ingest-classify-card">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold text-ink">Classification</h2>
              <span data-testid="ingest-status"><Badge>{job.status}</Badge></span>
            </div>
            <div className="space-y-2">
              {job.batch.files.map((f) => (
                <div
                  key={f.id}
                  className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface px-3 py-2 sm:flex-row sm:flex-wrap sm:items-center"
                >
                  <span className="min-w-0 flex-1 truncate font-mono text-sm text-ink">
                    {f.filename}
                  </span>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="info">{docTypeLabel(f.doc_type)}</Badge>
                    <Badge
                      variant={f.confidence >= 0.55 ? "success" : "warning"}
                      className="tabular-nums"
                    >
                      {(f.confidence * 100).toFixed(0)}%
                    </Badge>
                    {f.needs_user_confirm ? (
                      <span data-testid="ingest-needs-confirm">
                        <Badge variant="warning">Confirm type</Badge>
                      </span>
                    ) : null}
                    <Select
                      aria-label={`Document type for ${f.filename}`}
                      className="min-w-[11rem]"
                      value={overrides[f.id] ?? f.doc_type}
                      onChange={(e) =>
                        setOverrides((prev) => ({
                          ...prev,
                          [f.id]: e.target.value,
                        }))
                      }
                      options={DOC_TYPE_OPTIONS}
                      data-testid={`ingest-doc-type-${f.id}`}
                    />
                  </div>
                </div>
              ))}
            </div>
            {needsTypeConfirm ? (
              <div className="space-y-3 rounded-md border border-warning/30 bg-warning-subtle/40 p-3">
                <p className="text-xs text-muted">
                  What: low-confidence types need a human override. Why: the wrong
                  type changes models in the commit order. Next: pick the correct
                  type, give a short reason, then rebuild the plan.
                </p>
                <Input
                  label="Override reason"
                  hint="At least 3 characters. Stored in the session notice only."
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  placeholder="e.g. Filename is a vendor list, not customers"
                  data-testid="ingest-override-reason"
                  error={
                    overrideReason.length > 0 && overrideReasonTrimmed.length < 3
                      ? "Reason must be at least 3 characters."
                      : undefined
                  }
                />
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void applyOverrides()}
                  disabled={busy || !canApplyOverrides}
                  data-testid="ingest-apply-overrides"
                >
                  Apply type overrides and rebuild plan
                </Button>
              </div>
            ) : null}
          </Card>

          <Card className="space-y-3 p-4" data-testid="ingest-plan-card">
            <h2 className="text-sm font-semibold text-ink">Commit order</h2>
            <ol
              className="list-decimal space-y-2 pl-5 text-sm"
              data-testid="ingest-commit-order"
            >
              {(job.batch.plan?.steps ?? []).map((step) => (
                <li
                  key={step.step_index}
                  data-testid={`ingest-step-${step.step_index}`}
                  className="font-mono text-xs sm:text-sm"
                >
                  {step.models.join(", ")}
                  {step.parallel_ok ? (
                    <span className="ml-1 font-sans text-muted">(parallel ok)</span>
                  ) : null}
                </li>
              ))}
            </ol>
            {gaps.length > 0 ? (
              <Callout
                variant="warning"
                title="Unresolved gaps block commit"
                testId="ingest-gaps"
              >
                <p className="mb-2 text-xs">
                  What: missing references or units on this instance. Why: commit
                  would create incomplete rows. Next: fix the source file or map
                  values, then re-analyze.
                </p>
                <ul className="list-disc space-y-1 pl-4 text-xs">
                  {gaps.slice(0, 12).map((g, i) => (
                    <li key={`${g.model}-${g.field}-${i}`}>{g.message}</li>
                  ))}
                </ul>
              </Callout>
            ) : null}
            {job.batch.tables.map((t) => (
              <p key={t.id} className="text-xs text-muted tabular-nums">
                <span className="font-mono"><Term tech={t.model}>{t.model}</Term></span>: {t.rows?.length ?? 0}{" "}
                rows
                {t.warnings?.[0] ? ` · ${t.warnings[0]}` : ""}
              </p>
            ))}
          </Card>

          <Card className="space-y-3 p-4" data-testid="ingest-prefs-card">
            <h2 className="text-sm font-semibold text-ink">
              Notifications and CoA policy
            </h2>
            <fieldset className="space-y-2">
              <legend className="sr-only">Notify mode</legend>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="notify"
                  className="mt-1"
                  checked={notifyMode === "batch_summary"}
                  onChange={() => setNotifyMode("batch_summary")}
                  data-testid="ingest-notify-batch"
                />
                <span>
                  <span className="font-medium text-ink">Batch summary</span>
                  <span className="block text-xs text-muted">
                    Suppress per-record chatter and mail. Recommended for large
                    loads.
                  </span>
                </span>
              </label>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="notify"
                  className="mt-1"
                  checked={notifyMode === "individual"}
                  onChange={() => setNotifyMode("individual")}
                  data-testid="ingest-notify-individual"
                />
                <span>
                  <span className="font-medium text-ink">Individual notifications</span>
                  <span className="block text-xs text-muted">
                    Full Odoo tracking and mail per record.
                  </span>
                </span>
              </label>
            </fieldset>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await api.ingestPatchPrefs(connectionId, {
                    notify_mode: notifyMode,
                    allow_coa_as_is_default: allowCoaAsIs,
                  });
                  setNotice("Saved notify and CoA prefs for this connection.");
                } catch (err) {
                  setError(err instanceof Error ? err.message : String(err));
                } finally {
                  setBusy(false);
                }
              }}
              data-testid="ingest-save-prefs"
            >
              Save as connection default
            </Button>
            {hasFinancial ? (
              <>
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={allowCoaAsIs}
                    onChange={(e) => setAllowCoaAsIs(e.target.checked)}
                    data-testid="ingest-allow-coa-as-is"
                  />
                  <span>
                    Allow legacy CoA codes not in installed l10n packages
                    <span className="block text-xs text-muted">
                      Requires the financial confirm phrase on commit.
                    </span>
                  </span>
                </label>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  data-testid="ingest-coa-auto-remap"
                  onClick={async () => {
                    if (!job) return;
                    setBusy(true);
                    setError(null);
                    try {
                      const updated = await api.ingestCoaRemap(
                        connectionId,
                        job.id,
                        {
                          auto: true,
                          min_score: 0.45,
                        },
                      );
                      setJob(updated);
                      setNotice(
                        "Applied high-confidence CoA to l10n remaps.",
                      );
                    } catch (err) {
                      setError(
                        err instanceof Error ? err.message : String(err),
                      );
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  Auto-align CoA codes to l10n suggestions
                </Button>
                {Array.isArray(
                  (
                    job.batch.meta?.coa_alignment as
                      | { remap_suggestions?: unknown[] }
                      | undefined
                  )?.remap_suggestions,
                ) ? (
                  <ul className="list-disc space-y-1 pl-4 text-xs text-muted">
                    {(
                      (
                        job.batch.meta?.coa_alignment as {
                          remap_suggestions: Array<{
                            legacy_code: string;
                            suggested_code?: string;
                            suggested_name?: string;
                            score?: number;
                          }>;
                        }
                      ).remap_suggestions ?? []
                    )
                      .slice(0, 8)
                      .map((s) => (
                        <li key={s.legacy_code} className="font-mono tabular-nums">
                          {s.legacy_code} to {s.suggested_code ?? "(no match)"}
                          {s.suggested_name ? ` (${s.suggested_name})` : ""}
                          {s.score != null ? ` score=${s.score}` : ""}
                        </li>
                      ))}
                  </ul>
                ) : null}
              </>
            ) : null}
          </Card>

          <Card className="space-y-3 p-4" data-testid="ingest-actions-card">
            <h2 className="text-sm font-semibold text-ink">Test run and commit</h2>
            <p className="text-xs text-muted">
              Test run proves creates and updates with no writes. Commit is the
              only action that changes Odoo.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => void runDryRun()}
                disabled={busy}
                data-testid="ingest-dry-run-btn"
              >
                Test run
              </Button>
              <Button
                type="button"
                variant="primary"
                data-testid="ingest-commit-btn"
                onClick={() =>
                  hasFinancial ? setConfirmOpen(true) : void runCommit()
                }
                disabled={busy || gaps.length > 0}
              >
                Commit
              </Button>
            </div>
            {gaps.length > 0 ? (
              <p className="text-xs text-danger" data-testid="ingest-gap-block">
                Resolve gaps before commit.
              </p>
            ) : null}
            {log ? (
              <div
                className="rounded-md border border-border-subtle bg-surface-muted/50 p-3 text-xs"
                data-testid="ingest-commit-log"
                role="status"
              >
                <p className="font-medium text-ink tabular-nums">
                  {log.dry_run ? "Test run result (no writes)" : "Commit result (writes applied)"}
                  : created {log.created}, updated {log.updated}, failed{" "}
                  {log.failed}, skipped {log.skipped}
                </p>
                <ul className="mt-2 list-disc space-y-1 pl-4 text-muted">
                  {log.messages.slice(0, 8).map((m, i) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </Card>
        </>
      ) : null}

      <ConfirmDialogV2
        open={confirmOpen}
        title="Financial ingest confirmation"
        warning="CoA or opening-balance files can alter accounting data."
        risks={[
          "Incorrect accounts may break fiscal reports",
          "Opening balances create a DRAFT journal entry, never auto-posted",
          "Legacy CoA codes may diverge from the installed l10n package",
        ]}
        phrase={CONFIRM_PHRASE}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) => void runCommit(phrase)}
      />
    </OperateStudioChrome>
  );
}