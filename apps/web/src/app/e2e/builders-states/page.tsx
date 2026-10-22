"use client";

import { Suspense, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { CompareView } from "@/components/view-designer/Builder2d";
import { Note } from "@/components/view-designer/Note";
import { CanvasSkeleton } from "@/components/view-designer/Skeleton";
import vd from "@/components/view-designer/ViewDesigner.module.css";
import rd from "@/components/report-designer/ReportDesigner.module.css";
import type { Compare2d } from "@/lib/api/view-engine-2d";

/**
 * Builders stage 3: every state of the builder parts on one page (SPEC 8, hallmark 15.9).
 * `?theme=dark` for dark. Mock data only, no API calls.
 */

const CMP: Compare2d = {
  source: { major: 18, items: [{ node: "field:partner_id", tag: "field", label: "Customer", hidden: false }, { node: "field:client_order_ref", tag: "field", label: "Customer reference", hidden: false }] },
  target_now: { major: 20, items: [{ node: "field:partner_id", tag: "field", label: "Customer", hidden: false }, { node: "field:note", tag: "field", label: "Terms", hidden: true }] },
  target_after: { items: [{ node: "field:partner_id", tag: "field", label: "Customer", hidden: false }, { node: "field:client_order_ref", tag: "field", label: "Customer reference", hidden: false }] },
  changes: [{ kind: "added", node: "field:client_order_ref", text: "Added: Customer reference" }],
  still_different: [],
  problems: [],
  replaces: false,
  note: "Nothing changes until someone approves the move in the other database.",
};

function States() {
  const dark = useSearchParams().get("theme") === "dark";
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);
  return (
    <main className={vd.canvas} data-testid="builders-states">
      <section className={vd.device}>
        <div className={vd.panelBody}>
          <div className={vd.section}>
            <h2 className={vd.panelTitle}>Status lines</h2>
            <Note tone="info" role="status">3 records would be affected by this rule today.</Note>
            <Note tone="busy" role="status">Checking this screen…</Note>
            <Note tone="success">Nothing to fix.</Note>
            <Note tone="warning">This screen already has Ingenium changes here. Importing replaces them.</Note>
            <Note tone="danger" role="alert">Can&apos;t publish. The field Delivery date isn&apos;t on this model in your database. Remove it or pick another field.</Note>
          </div>
          <div className={vd.section}>
            <h2 className={vd.panelTitle}>Buttons</h2>
            <div className={vd.row}>
              <Button>Publish changes</Button>
              <Button variant="secondary">Preview as…</Button>
              <Button variant="ghost">Undo publish</Button>
              <Button disabled title="Nothing to publish yet">Publish changes</Button>
              <Button loading>Publishing…</Button>
            </div>
          </div>
          <div className={vd.section}>
            <h2 className={vd.panelTitle}>Controls</h2>
            <div className={vd.row}>
              <select className={vd.select} aria-label="Role" defaultValue=""><option value="">Pick a role…</option><option>Sales / User</option></select>
              <select className={vd.select} aria-label="Role (disabled)" disabled><option>Sales / User</option></select>
              <select className={vd.select} aria-label="Role (invalid)" aria-invalid="true"><option>Pick a role…</option></select>
              <button type="button" className={vd.chip}>Customer</button>
              <button type="button" className={vd.chip} disabled>Archived</button>
              <span className={vd.sampleBadge}>Sample</span>
            </div>
            <textarea className={vd.textarea} aria-label="Comment" placeholder="Write a comment" />
          </div>
          <div className={vd.section}>
            <h2 className={vd.panelTitle}>Lists</h2>
            <ul className={vd.list}>
              <li className={vd.listItem} data-kind="added">Added: Customer reference</li>
              <li className={vd.listItem} data-kind="removed">Removed: Email</li>
              <li className={vd.listItem} data-kind="changed">Changed: Phone (now required)</li>
              <li className={vd.listItem} data-hidden>Terms (hidden)</li>
            </ul>
            <ul className={vd.tree} role="tree" aria-label="Layers">
              <li className={vd.treeRow} role="treeitem" aria-selected="false" tabIndex={0}><span className={vd.treeLabel}>Customer</span><span className={vd.treeKind}>field</span></li>
              <li className={vd.treeRow} role="treeitem" aria-selected="true" tabIndex={-1}><span className={vd.treeLabel}>Order lines</span><span className={vd.treeKind}>tab</span></li>
            </ul>
          </div>
          <div className={vd.section}>
            <h2 className={vd.panelTitle}>Screen states</h2>
            <div className={vd.banner} role="status"><span>Showing an earlier version. Nothing is changed.</span><Button size="sm" variant="ghost">Back to now</Button></div>
            <p className={vd.muted}>No records yet, so fields show as empty. Insights → Sample data fills the preview with labelled samples.</p>
            <Note tone="danger" as="div" role="alert"><p>Can&apos;t open this screen. Odoo didn&apos;t answer in time.</p><Button size="sm">Try again</Button></Note>
            <CanvasSkeleton />
          </div>
          <div className={vd.section}>
            <h2 className={vd.panelTitle}>Move to another database</h2>
            <CompareView cmp={CMP} />
          </div>
        </div>
      </section>
      <section className={rd.paperDesk}>
        <div className={rd.paper}>
          <p className={rd.title}>Invoice footer</p>
          <ul className={rd.blocks}>
            <li className={rd.block}><span className={rd.title}>Bank details</span><span className={rd.small}>Shown on every page</span></li>
          </ul>
          <div className={rd.stockContent}>Odoo&apos;s own invoice content</div>
          <div className={rd.dropHint}>Drop a block here</div>
        </div>
      </section>
    </main>
  );
}

export default function BuildersStatesPage() {
  return (
    <Suspense>
      <States />
    </Suspense>
  );
}
