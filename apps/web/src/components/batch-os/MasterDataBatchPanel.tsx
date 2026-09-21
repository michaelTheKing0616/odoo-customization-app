"use client";

import { useCallback, useMemo, useState } from "react";
import {
  api,
  BatchOsJob,
  ConfirmationRequiredError,
} from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ConfirmDialogV2 } from "@/components/ui/ConfirmDialogV2";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Card } from "@/components/ui/layout-primitives";

const CONFIRM_PHRASE = "I understand the risks";

const PARTNER_TARGETS = [
  "name",
  "email",
  "vat",
  "ref",
  "phone",
  "mobile",
  "street",
  "city",
  "zip",
  "country_code",
  "is_company",
  "customer_rank",
  "supplier_rank",
] as const;

const PRODUCT_TARGETS = [
  "name",
  "default_code",
  "barcode",
  "list_price",
  "standard_price",
  "type",
  "uom",
  "categ",
  "sale_ok",
  "purchase_ok",
] as const;

type Kind = "partners" | "products";
type Props = { connectionId: string; initialKind?: Kind };

export function MasterDataBatchPanel({ connectionId, initialKind = "partners" }: Props) {
  const [kind, setKind] = useState<Kind>(initialKind);
  const [job, setJob] = useState<BatchOsJob | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [columnMap, setColumnMap] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const targets = kind === "products" ? PRODUCT_TARGETS : PARTNER_TARGETS;
  const headers = job?.headers ?? [];

  const onUpload = useCallback(async () => {
    if (!file) {
      setError("Choose a CSV or XLSX file first");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const next = await api.batchOsMasterIntake(connectionId, file, kind);
      setJob(next);
      setColumnMap(next.column_map || {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }, [connectionId, file, kind]);

  const runMap = useCallback(async () => {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.batchOsMasterMap(connectionId, {
        job_id: job.job_id,
        column_map: columnMap,
        kind,
      });
      setJob(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Map failed");
    } finally {
      setBusy(false);
    }
  }, [connectionId, job, columnMap, kind]);

  const runDryRun = useCallback(async () => {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      await api.batchOsMasterMap(connectionId, {
        job_id: job.job_id,
        column_map: columnMap,
        kind,
      });
      const next = await api.batchOsMasterDryRun(connectionId, {
        job_id: job.job_id,
        kind,
      });
      setJob(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dry-run failed");
    } finally {
      setBusy(false);
    }
  }, [connectionId, job, columnMap, kind]);

  const doApply = useCallback(
    async (confirmed: boolean) => {
      if (!job) return;
      setBusy(true);
      setError(null);
      try {
        const next = await api.batchOsMasterApply(connectionId, {
          job_id: job.job_id,
          kind,
          confirm_advanced: confirmed,
          confirm_phrase: confirmed ? CONFIRM_PHRASE : null,
        });
        setJob(next);
        setConfirmOpen(false);
      } catch (err) {
        if (err instanceof ConfirmationRequiredError) {
          setConfirmOpen(true);
        } else {
          setError(err instanceof Error ? err.message : "Apply failed");
        }
      } finally {
        setBusy(false);
      }
    },
    [connectionId, job, kind],
  );

  const blocking = useMemo(
    () => (job?.errors || []).filter((e) => e.code === "blocking"),
    [job],
  );

  return (
    <div className="space-y-4" data-testid="master-data-batch-panel">
      <Callout variant="info" title="Preview ≠ written">
        Dry-run proposes create/update via public RPC. Apply writes{" "}
        <code className="text-xs">res.partner</code> /{" "}
        <code className="text-xs">product.template</code>. Dedup by VAT/email/ref/name
        (partners) or code/barcode/name (products).
      </Callout>

      <div className="flex flex-wrap gap-2" data-testid="master-data-kind-tabs">
        <Button
          type="button"
          size="sm"
          variant={kind === "partners" ? "secondary" : "ghost"}
          onClick={() => {
            setKind("partners");
            setJob(null);
            setColumnMap({});
          }}
          data-testid="master-data-kind-partners"
        >
          Partners
        </Button>
        <Button
          type="button"
          size="sm"
          variant={kind === "products" ? "secondary" : "ghost"}
          onClick={() => {
            setKind("products");
            setJob(null);
            setColumnMap({});
          }}
          data-testid="master-data-kind-products"
        >
          Products
        </Button>
        <Badge
          variant={job?.risk === "L2" || job?.risk === "L3" ? "danger" : "default"}
          data-testid="master-data-risk-badge"
        >
          {job?.risk || "L1"}
        </Badge>
      </div>

      {error ? <ErrorNotice message={error} /> : null}

      <Card className="space-y-3 p-4">
        <p className="text-sm font-medium text-ink">1. Upload CSV / XLSX</p>
        <input
          type="file"
          accept=".csv,.xlsx,.xlsm,.txt"
          data-testid="master-data-batch-file"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <Button
          type="button"
          size="sm"
          variant="primary"
          disabled={busy || !file}
          onClick={() => void onUpload()}
          data-testid="master-data-upload"
        >
          Intake
        </Button>
      </Card>

      {job ? (
        <>
          <Card className="space-y-3 p-4" data-testid="master-data-map-step">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="info">{job.phase}</Badge>
              <span className="text-xs text-muted">
                {job.filename} · {job.raw_row_count} rows · job {job.job_id.slice(0, 8)}
              </span>
            </div>
            <p className="text-sm text-muted">{job.message}</p>
            <p className="text-sm font-medium text-ink">2. Column map</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {headers.map((h) => (
                <label key={h} className="flex items-center gap-2 text-xs">
                  <span className="w-28 truncate font-mono text-ink" title={h}>
                    {h}
                  </span>
                  <select
                    className="flex-1 rounded border border-border-subtle bg-surface px-2 py-1"
                    value={columnMap[h] || ""}
                    onChange={(e) =>
                      setColumnMap((prev) => ({ ...prev, [h]: e.target.value }))
                    }
                  >
                    <option value="">— skip —</option>
                    {targets.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => void runMap()}
                data-testid="master-data-map"
              >
                Map
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => void runDryRun()}
                data-testid="master-data-dry-run"
              >
                Dry-run
              </Button>
            </div>
          </Card>

          <Callout variant="warning" title="Preview ≠ written" data-testid="master-data-honesty">
            {job.honesty || "Dry-run never writes partners/products."}
          </Callout>

          {job.phase === "dry_run" || job.phase === "applied" ? (
            <p className="text-sm text-ink" data-testid="master-data-dry-run-result">
              {job.message}
            </p>
          ) : null}

          {blocking.length ? (
            <Callout variant="danger" title="Blocking errors">
              <ul className="list-disc pl-4 text-xs">
                {blocking.map((e, i) => (
                  <li key={`${e.row_index}-${i}`}>
                    row {e.row_index}
                    {e.field ? ` · ${e.field}` : ""}: {e.message}
                  </li>
                ))}
              </ul>
            </Callout>
          ) : null}

          <Card className="space-y-3 p-4" data-testid="master-data-apply-step">
            <p className="text-sm font-medium text-ink">3. Apply</p>
            <Button
              type="button"
              size="sm"
              variant="primary"
              disabled={busy || job.phase === "failed" || blocking.length > 0}
              onClick={() => void doApply(false)}
              data-testid="master-data-apply"
            >
              Apply writes
            </Button>
            {job.created_move_ids?.length ? (
              <p className="text-xs text-ink">Written ids: {job.created_move_ids.join(", ")}</p>
            ) : null}
          </Card>
        </>
      ) : null}

      <ConfirmDialogV2
        open={confirmOpen}
        title="Confirm master data batch apply"
        warning="Master data apply writes partners/products to live Odoo"
        phrase={CONFIRM_PHRASE}
        riskLevel="standard"
        risks={[
          "Writes res.partner / product.template on the live database",
          "Preview ≠ written — only Apply persists rows",
        ]}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void doApply(true)}
        busy={busy}
      />
    </div>
  );
}
