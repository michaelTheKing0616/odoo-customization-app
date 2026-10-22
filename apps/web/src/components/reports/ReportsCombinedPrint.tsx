"use client";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import type { ReportListRow } from "@/components/reports/ReportsListPanel";
import styles from "./ReportsPage.module.css";

export type MergeRow = { reportId: string; recordIds: string };

type ReportsCombinedPrintProps = {
  reports: ReportListRow[];
  mergeRows: MergeRow[];
  busy?: boolean;
  renderProbe: string | null;
  onChangeRows: (rows: MergeRow[]) => void;
  onProbe: () => void;
  onDownload: () => void;
};

/**
 * PDF-06 — Combined print strip (secondary to Save the printout).
 */
export function ReportsCombinedPrint({
  reports,
  mergeRows,
  busy,
  renderProbe,
  onChangeRows,
  onProbe,
  onDownload,
}: ReportsCombinedPrintProps) {
  return (
    <section
      className={styles.combined}
      data-testid="reports-combined-print"
    >
      <h2 className="text-[1.0625rem] font-semibold tracking-tight text-ink">Combined print</h2>
      <p className="mt-1 max-w-prose text-pretty text-sm text-muted">
        Render different QWeb PDFs server-side and merge into one download. Uses authenticated
        HTTP <code className="font-mono text-xs">/report/pdf</code> when RPC render is
        unavailable.
      </p>
      <div className="mt-4 space-y-3">
        {mergeRows.map((row, idx) => (
          <div key={idx} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
            <Select
              label="Report"
              value={row.reportId}
              onChange={(e) => {
                const next = [...mergeRows];
                next[idx] = { ...next[idx], reportId: e.target.value };
                onChangeRows(next);
              }}
              options={[
                { value: "", label: "— pick —" },
                ...reports.map((r) => ({
                  value: String(r.id),
                  label: `${r.name} (#${r.id})`,
                })),
              ]}
            />
            <Input
              label="Record ids"
              className="font-mono"
              value={row.recordIds}
              onChange={(e) => {
                const next = [...mergeRows];
                next[idx] = { ...next[idx], recordIds: e.target.value };
                onChangeRows(next);
              }}
              placeholder="1"
            />
            <Button
              type="button"
              variant="ghost"
              className="self-end text-danger"
              disabled={mergeRows.length <= 1}
              onClick={() => onChangeRows(mergeRows.filter((_, i) => i !== idx))}
            >
              Remove
            </Button>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          type="button"
          variant="secondary"
          onClick={() => onChangeRows([...mergeRows, { reportId: "", recordIds: "" }])}
        >
          Add report
        </Button>
        <Button type="button" variant="secondary" disabled={busy} onClick={onProbe}>
          Probe render path
        </Button>
        <Button type="button" variant="secondary" disabled={busy} onClick={onDownload}>
          Download merged PDF
        </Button>
      </div>
      {renderProbe ? (
        <p className="mt-3 text-xs text-muted" data-testid="reports-render-probe">
          {renderProbe}
        </p>
      ) : null}
    </section>
  );
}
