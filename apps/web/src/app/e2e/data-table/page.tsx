"use client";

import { BulkResultTable, type BulkRunResult } from "@/components/ui/BulkResultTable";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { Card, PageHeader } from "@/components/ui/layout-primitives";

type FieldRow = { id: string; model: string; field: string; size: number };

const LARGE_ROW_COUNT = 5000;
const SMALL_ROW_COUNT = 12;
const BULK_RECORD_COUNT = 120;
const MODELS = ["res.partner", "sale.order", "account.move", "stock.picking", "project.task"];

function makeFieldRows(count: number): FieldRow[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `f-${i}`,
    model: MODELS[i % MODELS.length],
    field: `x_field_${String(i).padStart(4, "0")}`,
    size: (i * 37) % 1000,
  }));
}

const fieldColumns: DataTableColumn<FieldRow>[] = [
  { id: "field", header: "Field", accessor: (r) => r.field, sortValue: (r) => r.field },
  { id: "model", header: "Model", accessor: (r) => r.model, sortValue: (r) => r.model },
  {
    id: "size",
    header: "Size",
    accessor: (r) => <span className="tabular-nums">{r.size}</span>,
    sortValue: (r) => r.size,
  },
];

const largeRows = makeFieldRows(LARGE_ROW_COUNT);
const smallRows = makeFieldRows(SMALL_ROW_COUNT);

const bulkResult: BulkRunResult = {
  run_id: "e2e-bulk",
  operation: "mass_edit",
  model: "res.partner",
  total: BULK_RECORD_COUNT,
  succeeded: BULK_RECORD_COUNT - BULK_RECORD_COUNT / 10,
  failed: BULK_RECORD_COUNT / 10,
  per_record: Array.from({ length: BULK_RECORD_COUNT }, (_, i) => {
    const ok = i % 10 !== 9;
    return {
      record_id: i + 1,
      display_name: `Partner ${i + 1}`,
      ok,
      error: ok ? null : "Access denied on res.partner",
    };
  }),
};

export default function DataTableE2EPage() {
  if (process.env.NEXT_PUBLIC_E2E !== "1") {
    return <p className="p-8">E2E harness only.</p>;
  }

  return (
    <main className="min-h-screen bg-surface p-4 sm:p-8" data-testid="data-table-page">
      <PageHeader
        title="Data tables"
        description="Tables over 50 rows render only the rows in view. Shorter tables render every row."
      />
      <div className="grid gap-4">
        <Card className="space-y-2 p-4" data-testid="data-table-large">
          <h2 className="text-sm font-medium text-ink">
            {LARGE_ROW_COUNT.toLocaleString("en-US")} fields (virtualized)
          </h2>
          <DataTable columns={fieldColumns} rows={largeRows} rowKey={(r) => r.id} />
        </Card>
        <Card className="space-y-2 p-4" data-testid="data-table-bulk">
          <h2 className="text-sm font-medium text-ink">
            Bulk result, {BULK_RECORD_COUNT} records (virtualized)
          </h2>
          <BulkResultTable result={bulkResult} />
        </Card>
        <Card className="space-y-2 p-4" data-testid="data-table-small">
          <h2 className="text-sm font-medium text-ink">{SMALL_ROW_COUNT} fields (plain table)</h2>
          <DataTable columns={fieldColumns} rows={smallRows} rowKey={(r) => r.id} />
        </Card>
      </div>
    </main>
  );
}
