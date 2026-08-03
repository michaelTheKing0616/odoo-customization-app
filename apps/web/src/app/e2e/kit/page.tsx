"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { BulkResultTable } from "@/components/ui/BulkResultTable";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { Combobox } from "@/components/ui/Combobox";
import { DataTable, type DataTableColumn } from "@/components/ui/DataTable";
import { DialogPanel } from "@/components/ui/Dialog";
import { DiffView } from "@/components/ui/DiffView";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Sheet } from "@/components/ui/Sheet";
import { StatusPill } from "@/components/ui/StatusPill";
import { Tabs } from "@/components/ui/Tabs";
import { Textarea } from "@/components/ui/Textarea";
import { Card, EmptyState, PageHeader, Skeleton } from "@/components/ui/layout-primitives";
import { IconExpert } from "@/components/ui/icons";

type DemoRow = { id: string; name: string; count: number };

const demoRows: DemoRow[] = [
  { id: "1", name: "res.partner", count: 42 },
  { id: "2", name: "sale.order", count: 12 },
];

const demoColumns: DataTableColumn<DemoRow>[] = [
  { id: "name", header: "Model", accessor: (r) => r.name, sortValue: (r) => r.name },
  { id: "count", header: "Fields", accessor: (r) => r.count, sortValue: (r) => r.count },
];

export default function KitE2EPage() {
  const [sheetOpen, setSheetOpen] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [combo, setCombo] = useState("partner");

  if (process.env.NEXT_PUBLIC_E2E !== "1") {
    return <p className="p-8">E2E harness only.</p>;
  }

  return (
    <main className="min-h-screen bg-surface p-8" data-testid="kit-page">
      <PageHeader title="Component kit" description="UIX-2 showcase" />
      <div className="grid gap-4">
        <Card className="space-y-3 p-4">
          <div className="flex flex-wrap gap-2">
            <Button variant="primary">Primary</Button>
            <Button variant="danger">Danger</Button>
            <Badge variant="ga">GA</Badge>
            <StatusPill kind="tier1-lock" />
            <StatusPill kind="hosting-online" />
          </div>
          <Input label="Input" placeholder="Model technical name" />
          <Textarea label="Textarea" placeholder="Describe your app…" />
          <Select
            label="Select"
            options={[
              { value: "form", label: "Form" },
              { value: "list", label: "List" },
            ]}
          />
          <Combobox
            options={[
              { value: "partner", label: "res.partner" },
              { value: "order", label: "sale.order" },
            ]}
            value={combo}
            onValueChange={setCombo}
          />
          <Callout variant="warning" title="Gating callout">
            What → why → options layout.
          </Callout>
          <ErrorNotice message="Sample API error for diagnose wiring." />
          <Skeleton className="h-8 w-40" />
          <EmptyState
            icon={<IconExpert className="h-8 w-8" />}
            title="Empty state"
            description="Designed first-class empty copy."
            action={<Button variant="secondary">Action</Button>}
          />
          <CodeBlock
            language="xml"
            code={'<xpath expr="//field[@name=\'name\']" position="after"/>'}
          />
          <DiffView before={"<field name='x'/>"} after={"<field name='x'/>\n<field name='y'/>"} />
          <DataTable columns={demoColumns} rows={demoRows} rowKey={(r) => r.id} selectable />
          <BulkResultTable
            result={{
              run_id: "demo",
              operation: "mass_edit",
              model: "res.partner",
              total: 2,
              succeeded: 1,
              failed: 1,
              per_record: [
                { record_id: 1, ok: true },
                { record_id: 2, ok: false, error: "Access denied" },
              ],
            }}
          />
          <Tabs
            items={[
              { value: "a", label: "Tab A", content: <p className="text-sm">Tab A content</p> },
              { value: "b", label: "Tab B", content: <p className="text-sm">Tab B content</p> },
            ]}
          />
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setSheetOpen(true)}>
              Open sheet
            </Button>
            <Button variant="secondary" onClick={() => setDialogOpen(true)}>
              Open dialog
            </Button>
          </div>
        </Card>
      </div>
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen} title="Sheet demo">
        <div className="p-4 text-sm">Right sheet panel</div>
      </Sheet>
      <DialogPanel open={dialogOpen} onOpenChange={setDialogOpen} title="Dialog demo">
        <p className="text-sm text-muted">Focus-trapped dialog content.</p>
      </DialogPanel>
    </main>
  );
}
