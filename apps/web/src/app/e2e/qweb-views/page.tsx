"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/layout-primitives";
import { QwebViewsCreateForm } from "@/components/qweb-views/QwebViewsCreateForm";
import { QwebViewsListPanel, type QwebViewListRow } from "@/components/qweb-views/QwebViewsListPanel";
import { QwebPaperPreview } from "@/components/qweb-views/QwebPaperPreview";
import {
  blocksToPreviewHtml,
  compileQwebViewBlocks,
  defaultQwebViewBlocks,
} from "@/components/qweb-views/qwebViewBlocks";
import styles from "@/components/qweb-views/QwebViewsPage.module.css";

/**
 * DOC-QWEB vision harness — paper desk + list chrome. Gated by NEXT_PUBLIC_E2E.
 */
type Shot = "desktop" | "empty" | "source" | "error";

const FIXTURES: QwebViewListRow[] = [
  {
    id: 31,
    name: "Partner card",
    key: "x_mod.partner_card",
    model: "res.partner",
  },
  {
    id: 32,
    name: "Sale document (report-bound)",
    key: "sale.report_saleorder_document",
    model: "sale.order",
    report_bound: true,
    report_name: "Quotation / Order",
  },
];

export default function QwebViewsHarnessPage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [shot, setShot] = useState<Shot>("desktop");
  const [selectedId, setSelectedId] = useState<number | null>(31);
  const [form, setForm] = useState({
    name: "Custom document",
    key: "x_mod.document",
    model: "res.partner",
  });

  const views = useMemo(() => (shot === "empty" ? [] : FIXTURES), [shot]);
  const selected = views.find((v) => v.id === selectedId) ?? FIXTURES[0];
  const preview = blocksToPreviewHtml(defaultQwebViewBlocks(selected.name));

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <main className={`${styles.page} mx-auto max-w-5xl p-6`} data-testid="qweb-views-e2e">
      <PageHeader
        title="QWeb views (vision)"
        description="DOC-QWEB harness — pasteboard paper template, not a raw textarea."
      />
      <div className="mt-4 flex flex-wrap gap-2">
        {(["desktop", "empty", "source", "error"] as Shot[]).map((s) => (
          <Button
            key={s}
            type="button"
            size="sm"
            variant={shot === s ? "primary" : "secondary"}
            onClick={() => setShot(s)}
            data-testid={`shot-${s}`}
          >
            {s}
          </Button>
        ))}
      </div>

      {shot === "error" ? (
        <div
          className="mt-6 rounded-md border border-danger/30 bg-danger-subtle p-4 text-sm"
          role="alert"
          data-testid="qweb-error"
        >
          <p className="font-semibold" data-testid="qweb-error-what">
            Unsafe QWeb refused: t-raw is not allowed in general QWeb views
          </p>
          <p className="mt-2 text-xs font-medium uppercase tracking-wide text-muted">Why</p>
          <p className="mt-1 text-muted" data-testid="qweb-error-why">
            The shared PDF-05 gate blocks t-raw / script / XXE / invent t-call before any write.
          </p>
          <p className="mt-2 text-xs font-medium uppercase tracking-wide text-muted">Next</p>
          <p className="mt-1 text-muted" data-testid="qweb-error-next">
            Remove the unsafe directive, or express the content with grounded t-field blocks.
          </p>
        </div>
      ) : (
        <div className="mt-6 space-y-5">
          <QwebViewsCreateForm
            form={form}
            canSubmit
            onChange={setForm}
            onSubmit={(e) => e.preventDefault()}
          />
          <div className={styles.workbench} data-testid="qweb-views-workbench">
            <QwebViewsListPanel
              views={views}
              selectedId={selectedId}
              hydrated
              onSelect={setSelectedId}
              embedded
            />
            <div className={styles.editorPane}>
              {shot === "source" ? (
                <textarea
                  className="min-h-[12rem] w-full p-3 font-mono text-xs"
                  defaultValue={compileQwebViewBlocks(defaultQwebViewBlocks(selected.name))}
                  data-testid="qweb-source-xml"
                  readOnly
                />
              ) : (
                <QwebPaperPreview
                  title={selected.name}
                  keyLabel={selected.key}
                  model={selected.model}
                  bodyHtml={preview}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
