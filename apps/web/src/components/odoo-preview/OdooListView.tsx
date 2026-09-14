"use client";

import type { PreviewListView } from "@/lib/draft-form-preview";

type OdooListViewProps = {
  view: PreviewListView;
};

const SAMPLE_ROWS = [
  { tone: "default" as const, cells: ["Sample record", "Draft", "Acme Corp", "120.00"] },
  { tone: "danger" as const, cells: ["Urgent follow-up", "Cancelled", "Beta LLC", "0.00"] },
  { tone: "muted" as const, cells: ["Archived item", "Done", "Legacy Co", "45.00"] },
];

export function OdooListView({ view }: OdooListViewProps) {
  return (
    <div className="odoo-form-canvas overflow-hidden shadow-sm" data-testid="odoo-list-view">
      <div className="odoo-form-header flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-[var(--odoo-primary)]">{view.title}</span>
        <span className="odoo-btn-secondary">list</span>
      </div>
      <div className="p-3">
        {view.decorations ? (
          <div className="mb-3 grid gap-2 text-xs text-[var(--odoo-muted)] sm:grid-cols-3">
            {view.decorations.danger ? (
              <div>
                decoration-danger
                <div className="mt-1 font-mono">{view.decorations.danger}</div>
              </div>
            ) : null}
            {view.decorations.info ? (
              <div>
                decoration-info
                <div className="mt-1 font-mono">{view.decorations.info}</div>
              </div>
            ) : null}
            {view.decorations.muted ? (
              <div>
                decoration-muted
                <div className="mt-1 font-mono">{view.decorations.muted}</div>
              </div>
            ) : null}
          </div>
        ) : null}
        <div className="overflow-x-auto border border-[var(--odoo-border)] bg-white">
          <table className="odoo-list-table" data-testid="list-preview-table">
            <thead>
              <tr>
                {view.columns.map((col) => (
                  <th key={col.id}>{col.string || col.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {SAMPLE_ROWS.map((row, idx) => (
                <tr
                  key={idx}
                  className={
                    row.tone === "danger"
                      ? "odoo-list-row-danger"
                      : row.tone === "muted"
                        ? "odoo-list-row-muted"
                        : undefined
                  }
                >
                  {view.columns.map((col, colIdx) => (
                    <td key={col.id}>{row.cells[colIdx] || "—"}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
