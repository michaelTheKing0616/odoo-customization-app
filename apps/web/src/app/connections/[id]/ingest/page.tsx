"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  api,
  ConfirmationRequiredError,
  IngestJobOut,
} from "@/lib/api";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Card, PageHeader } from "@/components/ui/layout-primitives";

const CONFIRM_PHRASE = "I understand the risks";
const DOC_TYPES = [
  "coa",
  "bom",
  "product_catalog",
  "customer_list",
  "vendor_list",
  "price_list",
  "employee_roster",
  "opening_trial_balance",
  "inventory_count",
  "other",
] as const;

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

  const [businessName, setBusinessName] = useState("");
  const [productLines, setProductLines] = useState("Widget | W-01 | 19.99");
  const [contacts, setContacts] = useState("Jane Doe | jane@example.com | +1234");
  const [expenseCats, setExpenseCats] = useState("Office supplies\nTravel");

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
  const hasFinancial = job?.batch.files.some((f) =>
    ["coa", "opening_trial_balance"].includes(f.doc_type),
  );
  const log = job?.batch.commit_log;

  async function uploadAndPlan() {
    if (!files.length) {
      setError("Select at least one CSV, XLSX, PDF, or image file.");
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
      setNotice("Files classified, extracted, and commit order planned.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function applyOverrides() {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.ingestOverride(connectionId, job.id, {
        force_doc_types: overrides,
      });
      setJob(updated);
      setNotice("Classification overridden — plan rebuilt.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function runInterview() {
    setBusy(true);
    setError(null);
    try {
      const created = await api.ingestCreateInterviewJob(connectionId, {
        business_name: businessName,
        product_type: "mixed",
        product_lines: productLines.split("\n").filter(Boolean),
        starter_contacts: contacts.split("\n").filter(Boolean),
        expense_categories: expenseCats.split("\n").filter(Boolean),
      });
      setJob(created);
      setNotice("Expert interview batch planned — same dry-run/commit path as uploads.");
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
      setNotice("Dry-run complete — no writes performed.");
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
      setNotice("Commit finished.");
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

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6" data-testid="ingest-page">
      <PageHeader
        title="Universal ingest"
        description="Upload CSV/XLSX/PDF/images or build starter data with Expert — classify, order, dry-run, commit."
      />

      {visionMsg && (
        <Callout variant="info" title="Vision OCR">
          {visionMsg}
        </Callout>
      )}

      {error && <ErrorNotice message={error} />}
      {notice && (
        <Callout variant="info" title="Done">
          {notice}
        </Callout>
      )}

      <Card className="space-y-4 p-4">
        <p className="text-sm font-medium text-ink">1. Upload files</p>
        <input
          type="file"
          multiple
          accept=".csv,.xlsx,.xlsm,.pdf,.png,.jpg,.jpeg,.webp,text/csv,application/pdf,image/*"
          data-testid="ingest-file-input"
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          className="block w-full text-sm"
        />
        <Button
          type="button"
          data-testid="ingest-analyze-btn"
          onClick={uploadAndPlan}
          disabled={busy || !files.length}
        >
          {busy ? "Working…" : "Analyze & plan"}
        </Button>
      </Card>

      <Card className="space-y-3 p-4">
        <p className="text-sm font-medium text-ink">Or: Build starter data with Expert</p>
        <Input
          placeholder="Business name"
          value={businessName}
          onChange={(e) => setBusinessName(e.target.value)}
        />
        <textarea
          className="w-full rounded border border-border p-2 text-sm"
          rows={2}
          value={productLines}
          onChange={(e) => setProductLines(e.target.value)}
          placeholder="Products: Name | SKU | Price"
        />
        <textarea
          className="w-full rounded border border-border p-2 text-sm"
          rows={2}
          value={contacts}
          onChange={(e) => setContacts(e.target.value)}
          placeholder="Contacts: Name | Email | Phone"
        />
        <textarea
          className="w-full rounded border border-border p-2 text-sm"
          rows={2}
          value={expenseCats}
          onChange={(e) => setExpenseCats(e.target.value)}
          placeholder="Expense categories (guidance → product.category, not CoA)"
        />
        <Button type="button" data-testid="ingest-interview-btn" onClick={runInterview} disabled={busy}>
          Build from interview
        </Button>
      </Card>

      {job && (
        <>
          <Card className="space-y-3 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium text-ink">2. Classification</p>
              <Badge data-testid="ingest-status">{job.status}</Badge>
            </div>
            <div className="space-y-2">
              {job.batch.files.map((f) => (
                <div
                  key={f.id}
                  className="flex flex-wrap items-center gap-2 rounded border border-border px-3 py-2 text-sm"
                >
                  <span className="font-mono">{f.filename}</span>
                  <Badge variant="info">{f.doc_type}</Badge>
                  <Badge variant={f.confidence >= 0.55 ? "success" : "warning"}>
                    {(f.confidence * 100).toFixed(0)}%
                  </Badge>
                  {f.needs_user_confirm && (
                    <Badge variant="warning" data-testid="ingest-needs-confirm">
                      confirm type
                    </Badge>
                  )}
                  <select
                    className="rounded border border-border px-2 py-1 text-xs"
                    value={overrides[f.id] ?? f.doc_type}
                    onChange={(e) =>
                      setOverrides((prev) => ({ ...prev, [f.id]: e.target.value }))
                    }
                    data-testid={`ingest-doc-type-${f.id}`}
                  >
                    {DOC_TYPES.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
            {job.batch.files.some((f) => f.needs_user_confirm) && (
              <Button type="button" variant="secondary" onClick={applyOverrides} disabled={busy}>
                Apply type overrides & rebuild plan
              </Button>
            )}
          </Card>

          <Card className="space-y-3 p-4">
            <p className="text-sm font-medium text-ink">3. Commit order</p>
            <ol className="list-decimal space-y-2 pl-5 text-sm" data-testid="ingest-commit-order">
              {(job.batch.plan?.steps ?? []).map((step) => (
                <li key={step.step_index} data-testid={`ingest-step-${step.step_index}`}>
                  {step.models.join(", ")}
                  {step.parallel_ok ? " (parallel ok)" : ""}
                </li>
              ))}
            </ol>
            {gaps.length > 0 && (
              <Callout variant="warning" title="Unresolved gaps" data-testid="ingest-gaps">
                <ul className="list-disc pl-4 text-xs">
                  {gaps.slice(0, 12).map((g, i) => (
                    <li key={`${g.model}-${g.field}-${i}`}>{g.message}</li>
                  ))}
                </ul>
              </Callout>
            )}
            {job.batch.tables.map((t) => (
              <p key={t.id} className="text-xs text-muted">
                {t.model}: {t.rows?.length ?? 0} rows
                {t.warnings?.[0] ? ` — ${t.warnings[0]}` : ""}
              </p>
            ))}
          </Card>

          <Card className="space-y-3 p-4">
            <p className="text-sm font-medium text-ink">4. Notifications & CoA policy</p>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="notify"
                checked={notifyMode === "batch_summary"}
                onChange={() => setNotifyMode("batch_summary")}
                data-testid="ingest-notify-batch"
              />
              Batch summary (suppress per-record chatter/mail) — recommended
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="notify"
                checked={notifyMode === "individual"}
                onChange={() => setNotifyMode("individual")}
                data-testid="ingest-notify-individual"
              />
              Individual notifications (full Odoo tracking/mail)
            </label>
            <Button
              type="button"
              variant="secondary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await api.ingestPatchPrefs(connectionId, {
                    notify_mode: notifyMode,
                    allow_coa_as_is_default: allowCoaAsIs,
                  });
                  setNotice("Saved notify/CoA prefs for this connection.");
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
            {hasFinancial && (
              <>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={allowCoaAsIs}
                    onChange={(e) => setAllowCoaAsIs(e.target.checked)}
                    data-testid="ingest-allow-coa-as-is"
                  />
                  Allow legacy CoA codes not in installed l10n_* (requires financial confirm)
                </label>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  data-testid="ingest-coa-auto-remap"
                  onClick={async () => {
                    if (!job) return;
                    setBusy(true);
                    setError(null);
                    try {
                      const updated = await api.ingestCoaRemap(connectionId, job.id, {
                        auto: true,
                        min_score: 0.45,
                      });
                      setJob(updated);
                      setNotice("Applied high-confidence CoA → l10n remaps.");
                    } catch (err) {
                      setError(err instanceof Error ? err.message : String(err));
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  Auto-align CoA codes to l10n suggestions
                </Button>
                {Array.isArray(
                  (job.batch.meta?.coa_alignment as { remap_suggestions?: unknown[] } | undefined)
                    ?.remap_suggestions,
                ) && (
                  <ul className="list-disc pl-4 text-xs text-muted">
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
                        <li key={s.legacy_code}>
                          {s.legacy_code} → {s.suggested_code ?? "(no match)"}{" "}
                          {s.suggested_name ? `(${s.suggested_name})` : ""}{" "}
                          {s.score != null ? `score=${s.score}` : ""}
                        </li>
                      ))}
                  </ul>
                )}
              </>
            )}
          </Card>

          <Card className="space-y-3 p-4">
            <p className="text-sm font-medium text-ink">5. Dry-run & commit</p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="secondary" onClick={runDryRun} disabled={busy}>
                Dry-run
              </Button>
              <Button
                type="button"
                data-testid="ingest-commit-btn"
                onClick={() => (hasFinancial ? setConfirmOpen(true) : runCommit())}
                disabled={busy || gaps.length > 0}
              >
                Commit
              </Button>
            </div>
            {gaps.length > 0 && (
              <p className="text-xs text-danger" data-testid="ingest-gap-block">
                Resolve gaps before commit.
              </p>
            )}
            {log && (
              <div className="rounded border border-border p-3 text-xs" data-testid="ingest-commit-log">
                <p>
                  {log.dry_run ? "Dry-run" : "Commit"}: created {log.created}, updated{" "}
                  {log.updated}, failed {log.failed}, skipped {log.skipped}
                </p>
                <ul className="mt-1 list-disc pl-4">
                  {log.messages.slice(0, 8).map((m, i) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              </div>
            )}
          </Card>
        </>
      )}

      <ConfirmDialogV2
        open={confirmOpen}
        title="Financial ingest confirmation"
        warning="CoA or opening-balance files can alter accounting data."
        risks={[
          "Incorrect accounts may break fiscal reports",
          "Opening balances create a DRAFT journal entry — never auto-posted",
          "Legacy CoA codes may diverge from l10n_* package",
        ]}
        phrase={CONFIRM_PHRASE}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) => runCommit(phrase)}
      />
    </div>
  );
}
