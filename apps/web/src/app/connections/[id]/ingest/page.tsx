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

  const [businessName, setBusinessName] = useState("");
  const [productLines, setProductLines] = useState("Widget | W-01 | 19.99");
  const [contacts, setContacts] = useState("Jane Doe | jane@example.com | +1234");

  useEffect(() => {
    api.ingestVisionStatus(connectionId).then((s) => setVisionMsg(s.message)).catch(() => null);
  }, [connectionId]);

  const gaps = job?.batch.plan?.gaps ?? job?.batch.gaps ?? [];
  const hasFinancial = job?.batch.files.some((f) =>
    ["coa", "opening_trial_balance"].includes(f.doc_type),
  );

  async function uploadAndPlan() {
    if (!files.length) {
      setError("Select at least one CSV, XLSX, or PDF file.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await api.ingestCreateJob(connectionId, files);
      setJob(created);
      setNotice("Files classified, extracted, and commit order planned.");
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
      const updated = await api.ingestDryRun(connectionId, job.id);
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
        description="Upload CSV/XLSX/PDF or build starter data with Expert interview — classify, order, dry-run, commit."
      />

      {visionMsg && (
        <Callout variant="info" title="Vision OCR">
          {visionMsg}
        </Callout>
      )}

      {error && <ErrorNotice message={error} />}
      {notice && (
        <Callout variant="success" title="Done">
          {notice}
        </Callout>
      )}

      <Card className="space-y-4 p-4">
        <p className="text-sm font-medium text-ink">1. Upload files</p>
        <input
          type="file"
          multiple
          accept=".csv,.xlsx,.xlsm,.pdf,text/csv,application/pdf"
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
                </div>
              ))}
            </div>
          </Card>

          <Card className="space-y-3 p-4">
            <p className="text-sm font-medium text-ink">3. Commit order</p>
            <ol className="list-decimal space-y-2 pl-5 text-sm" data-testid="ingest-commit-order">
              {(job.batch.plan?.steps ?? []).map((step) => (
                <li key={step.step_index} data-testid={`ingest-step-${step.step_index}`}>
                  {step.models.join(", ")}
                </li>
              ))}
            </ol>
            {gaps.length > 0 && (
              <Callout variant="warning" title="Unresolved gaps" data-testid="ingest-gaps">
                <ul className="list-disc pl-4 text-xs">
                  {gaps.slice(0, 8).map((g, i) => (
                    <li key={`${g.model}-${g.field}-${i}`}>{g.message}</li>
                  ))}
                </ul>
              </Callout>
            )}
          </Card>

          <Card className="space-y-3 p-4">
            <p className="text-sm font-medium text-ink">4. Dry-run & commit</p>
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
          </Card>
        </>
      )}

      <ConfirmDialogV2
        open={confirmOpen}
        title="Financial ingest confirmation"
        warning="CoA or opening-balance files can alter accounting data."
        risks={[
          "Incorrect accounts may break fiscal reports",
          "Opening balances affect trial balance",
        ]}
        phrase={CONFIRM_PHRASE}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={(phrase) => runCommit(phrase)}
      />
    </div>
  );
}
