"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import type { BlockType, Starter, VisualCompareOut } from "@/lib/api/view-engine-2b";
import { addBlock, blockCount, newBlock } from "@/lib/viewDesigner2b";
import { PlacementsEditor, type BlockContext } from "./BlockEditor";
import { AIEditBox } from "./AIEditBox";
import { BlockSets } from "./BlockSets";
import { EmailDesigner } from "./EmailDesigner";
import { CompanyBrands, FromDocument } from "./Report2c";
import { useReportDesigner } from "./useReportDesigner";
import { Note } from "../view-designer/Note";
import { WriteModeNote } from "../view-designer/WriteModeNote";
import styles from "./ReportDesigner.module.css";
import { noteWriteRefusal } from "../view-designer/writeModeSignal";

const ADDABLE: BlockType[] = ["text", "heading", "field", "label_field", "divider", "spacer", "line_table", "qr", "barcode", "signature", "image_field", "watermark", "page_break"];
const ADD_LABEL: Record<BlockType, string> = { heading: "Heading", text: "Text", field: "Field value", label_field: "Label and value", divider: "Divider", spacer: "Space", line_table: "Lines table", qr: "QR code", barcode: "Barcode", signature: "Signature", image_field: "Picture", watermark: "Watermark", page_break: "Page break" };

const CHECK_LEVEL: Record<string, string> = { overflow: "Text runs past the page edge", image: "A picture is too large for the page", split: "A table of lines is split across pages", pages: "This prints on more pages than before" };

/** Report Designer: blocks anywhere, real PDFs from Odoo, checks, compare, brand and emails. */
export function ReportDesignerShell({ connectionId }: { connectionId: string }) {
  const s = useReportDesigner(connectionId);
  const [mode, setMode] = useState<"print" | "email">("print");
  const [showMargins, setShowMargins] = useState(false); // 131
  const records = s.data?.records ?? [];
  const recIdx = records.findIndex((r) => r.id === s.recordId);
  const slots = s.layout?.slots ?? [];
  const count = blockCount(s.placements);

  const ctx: BlockContext = {
    fields: s.fields,
    lineFields: s.layout?.line_fields ?? [],
    loadColumns: async (field) => (await api.linesFields(connectionId, s.reportId ?? 0, field)).columns,
  };
  const add = (type: BlockType) => {
    if (!slots.some((sl) => sl.id === s.slot)) {
      toast("This print layout has no safe place to add content yet.");
      return;
    }
    const first = s.fields.find((f) => ["char", "text", "many2one"].includes(f.type))?.name ?? "name";
    s.setPlacements(addBlock(s.placements, s.slot, newBlock(type, first)));
  };

  return (
    <div className={styles.shell} data-testid="report-designer">
      <header className={styles.topBar}>
        <div className={styles.inline} role="tablist" aria-label="Design">
          <Button size="sm" variant="ghost" role="tab" aria-selected={mode === "print"} onClick={() => setMode("print")}>Print layouts</Button>
          <Button size="sm" variant="ghost" role="tab" aria-selected={mode === "email"} onClick={() => setMode("email")}>Emails</Button>
        </div>
        {mode === "print" ? (
          <>
            <label className={styles.inline}>
              <span className={styles.small}>Print layout</span>
              <select value={s.reportId ?? ""} onChange={(e) => s.setReportId(Number(e.target.value) || null)} disabled={!s.data?.reports.length}>
                {(s.data?.reports ?? []).map((r) => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </select>
            </label>
            <div className={styles.inline} aria-label="Sample records">
              <Button size="sm" variant="ghost" aria-label="Previous record" disabled={recIdx <= 0} onClick={() => s.setRecordId(records[recIdx - 1]?.id ?? null)}>‹</Button>
              <span data-testid="rd-record-pos">
                {records.length ? `${records[recIdx]?.display_name ?? ""} (${recIdx + 1} of ${records.length})` : "No records yet"}
              </span>
              <Button size="sm" variant="ghost" aria-label="Next record" disabled={recIdx < 0 || recIdx >= records.length - 1} onClick={() => s.setRecordId(records[recIdx + 1]?.id ?? null)}>›</Button>
            </div>
            {s.data ? <span className={styles.small}>Odoo {s.data.major}</span> : null}
            <div className={styles.actions}>
              <Button size="sm" variant="secondary" loading={s.proofing} disabled={!s.recordId} onClick={() => void s.showProof()}>
                {s.proofing ? "Printing…" : "Show the printed page"}
              </Button>
              <Button size="sm" variant="ghost" loading={s.comparing} disabled={!s.recordId || !s.dirty} onClick={() => void s.runCompare()} data-testid="rd-compare">
                Compare before and after
              </Button>
              <Button size="sm" variant="primary" loading={s.publishing} disabled={!count || !s.recordId || !slots.length || !s.ready || s.offline} onClick={() => void s.publish()} data-testid="rd-publish">
                {s.publishing ? "Publishing…" : count ? `Publish changes (${count})` : "Publish changes"}
              </Button>
            </div>
          </>
        ) : null}
      </header>

      {mode === "email" ? <EmailDesigner connectionId={connectionId} model={s.model} /> : (
        <>
          <aside className={styles.left} aria-label="Blocks" inert={s.offline || undefined}>
            <div className={styles.panel}>
              <h2 className={styles.title}>Where</h2>
              {slots.length ? (
                <fieldset className={styles.stack}>
                  <legend className={styles.srOnly}>Where the new content goes</legend>
                  {slots.map((sl) => (
                    <label key={sl.id} className={styles.inline}>
                      <input type="radio" name="rd-slot" value={sl.id} checked={s.slot === sl.id} onChange={() => s.setSlot(sl.id)} />
                      {sl.label}
                    </label>
                  ))}
                </fieldset>
              ) : (
                <p className={styles.small}>This print layout has no safe place to add content yet.</p>
              )}
              <h2 className={styles.title}>Add</h2>
              <div className={styles.stack}>
                {(s.layout?.blocks ?? ADDABLE).map((t) => (
                  <Button key={t} size="sm" variant="ghost" onClick={() => add(t)}>{ADD_LABEL[t]}</Button>
                ))}
              </div>
              {s.reportId ? <Gallery connectionId={connectionId} reportId={s.reportId} onUse={(st) => s.setPlacements(st.placements)} /> : null}
              {s.layout?.layer?.active ? (
                <Button size="sm" variant="ghost" onClick={() => { if (window.confirm("Turn off every Ingenium change on this document? Odoo's own layout stays.")) void s.removeAll(); }}>
                  Turn off all changes
                </Button>
              ) : null}
            </div>
          </aside>

          <main className={styles.paperDesk} aria-label="Layout">
            {s.loading ? <Note tone="busy" role="status">Loading the print layout from Odoo…</Note> : null}
            {s.offline ? (
              <Note tone="warning" as="div" role="status" data-testid="rd-offline">
                <p>You&apos;re offline. This is the last version of the print layout Ingenium loaded, read-only until you reconnect.</p>
                <Button size="sm" onClick={() => void s.reload()}>Retry</Button>
              </Note>
            ) : null}
            <WriteModeNote connectionId={connectionId} />
            {s.loadError ? (
              <Note tone="danger" as="div" role="alert">
                <p>Can&apos;t open this print layout. {s.loadError}</p>
                <Button size="sm" onClick={() => void s.reload()}>Try again</Button>
              </Note>
            ) : null}
            {s.layout?.earlier_changes ? (
              <Note tone="warning" role="note" data-testid="rd-earlier">
                This document already has Ingenium changes from an earlier version. Publishing replaces them. Use Turn off all changes first if you want to see them again.
              </Note>
            ) : null}
            <div className={styles.paper} data-testid="rd-paper">
              <PlacementsEditor
                slots={slots}
                placements={s.placements}
                activeSlot={s.slot}
                onActiveSlot={s.setSlot}
                onChange={s.setPlacements}
                ctx={ctx}
                stockLabel={`Odoo's ${s.data?.report?.name ?? "document"} content`}
              />
            </div>
          </main>

          <aside className={styles.right} aria-label="Printed page">
            <h2 className={styles.title}>Printed page</h2>
            {s.variantList.length ? (
              <label className={styles.inline}>
                <span className={styles.small}>Preview in</span>
                <select aria-label="Language, currency or company" value={s.variant?.key ?? ""} onChange={(e) => s.setVariant(s.variantList.find((v) => v.key === e.target.value) ?? null)}>
                  <option value="">As printed</option>
                  {s.variantList.map((v) => <option key={v.key} value={v.key}>{v.label}</option>)}
                </select>
              </label>
            ) : null}
            {s.drafting ? <Note tone="busy" role="status" data-testid="rd-updating">Updating the report preview…</Note> : null}
            {s.draftNote ? <p className={styles.small} role="note">{s.draftNote}</p> : null}
            {s.checks.length ? (
              <ul className={styles.notice} role="note" data-testid="rd-checks">
                {s.checks.map((c, i) => <li key={i}>{CHECK_LEVEL[c.kind] ?? c.text}{c.page ? ` (page ${c.page})` : ""}</li>)}
              </ul>
            ) : null}
            {s.compare ? <Compare out={s.compare} onClose={s.closeCompare} loadVisual={s.loadVisualCompare} /> : null}
            {s.proofUrl ? (
              <>
                <p className={styles.small} data-testid="rd-proof-pages">
                  {s.proofPages === 1 ? "1 page" : `${s.proofPages} pages`}, printed by Odoo
                  {s.isDraft ? ", draft, only you see it" : ""}
                </p>
                <label className={styles.small} data-testid="rd-margins-toggle">
                  <input type="checkbox" checked={showMargins} onChange={(e) => setShowMargins(e.target.checked)} /> Show margins
                </label>
                <div className={styles.desk} data-testid="rd-paper-desk">
                  <div className={styles.paperFrame}>
                    <iframe key={s.proofUrl} title="Printed page from Odoo" src={`${s.proofUrl}${s.proofUrl.includes("#") ? "" : "#view=Fit&toolbar=0"}`} className={`${styles.proof} ${styles.paper}`} />
                    {/* 131: Odoo's standard A4 margins (top 40, bottom 28, sides 7 mm), drawn over the proof as a dashed guide. */}
                    {showMargins ? <div className={styles.margins} aria-hidden="true" data-testid="rd-margins" /> : null}
                  </div>
                </div>
              </>
            ) : (
              <p className={styles.small}>Choose a record and select Show the printed page to see the real PDF from Odoo.</p>
            )}
            {s.reportId ? (
              <AIEditBox what="report" placements={s.placements} onPlacements={s.setPlacements}
                propose={(text, placements) => api.aiEdit(connectionId, { report_id: s.reportId ?? 0, text, placements })}
                apply={(placements, ops) => api.aiApply(connectionId, { report_id: s.reportId ?? 0, placements, ops })} />
            ) : null}
            {s.reportId ? <BrandBox connectionId={connectionId} /> : null}
            {s.reportId ? <CompanyBrands connectionId={connectionId} /> : null}
            {s.reportId ? <FromDocument connectionId={connectionId} reportId={s.reportId} onDraft={(p) => s.setPlacements(p)} /> : null}
            {s.reportId ? <PageNumbers connectionId={connectionId} companyId={s.variant?.companyId ?? null} /> : null}
            {s.data?.report?.model ? (
              <BlockSets connectionId={connectionId} model={s.data.report.model} placements={s.placements} email={false} onUse={(p) => s.setPlacements([...s.placements, ...p])} />
            ) : null}
          </aside>
        </>
      )}
    </div>
  );
}

function Gallery({ connectionId, reportId, onUse }: { connectionId: string; reportId: number; onUse: (s: Starter) => void }) {
  const [starters, setStarters] = useState<Starter[] | null>(null);
  const open = () => api.gallery(connectionId, reportId).then((o) => setStarters(o.starters)).catch((e) => toast.error(e instanceof Error ? e.message : "Couldn't load starters."));
  return (
    <div className={styles.stack} data-testid="rd-gallery">
      <Button size="sm" variant="ghost" onClick={() => (starters ? setStarters(null) : void open())}>Start from a template…</Button>
      {starters ? (
        starters.length ? (
          starters.map((st) => <Button key={st.key} size="sm" variant="ghost" onClick={() => onUse(st)}>{st.label}</Button>)
        ) : <p className={styles.small}>No templates fit this document in this database.</p>
      ) : null}
    </div>
  );
}

function Compare({ out, onClose, loadVisual }: { out: { out: { diff: { same: boolean; pages_before: number; pages_after: number; pages: Array<{ page: number; added: string[]; removed: string[] }> } }; before: string; after: string }; onClose: () => void; loadVisual: () => Promise<VisualCompareOut | null> }) {
  const d = out.out.diff;
  const [mode, setMode] = useState<"text" | "pictures">("text");
  const [visual, setVisual] = useState<VisualCompareOut["visual"] | null>(null);
  const [loading, setLoading] = useState(false);
  const [sideBySide, setSideBySide] = useState(false);
  const showPictures = async () => {
    setMode("pictures");
    if (visual || loading) return;
    setLoading(true);
    const v = await loadVisual();
    setLoading(false);
    if (v) setVisual(v.visual);
  };
  return (
    <div className={styles.stack} data-testid="rd-compare-view">
      <div className={styles.inline} role="tablist" aria-label="How to compare">
        <Button size="sm" variant={mode === "text" ? "secondary" : "ghost"} role="tab" aria-selected={mode === "text"} onClick={() => setMode("text")}>Text</Button>
        <Button size="sm" variant={mode === "pictures" ? "secondary" : "ghost"} role="tab" aria-selected={mode === "pictures"} loading={loading} onClick={() => void showPictures()} data-testid="rd-compare-pictures">Pictures</Button>
      </div>
      {mode === "text" ? (
        <>
          <p className={styles.small}>{d.same ? "No difference in the text." : "Text that changed:"} {d.pages_before} → {d.pages_after} pages.</p>
          <ul className={styles.blocks}>
            {d.pages.map((p) => (
              <li key={p.page} className={styles.small}>
                Page {p.page}
                {p.added.length ? <span> added: {p.added.join(", ")}</span> : null}
                {p.removed.length ? <span> removed: {p.removed.join(", ")}</span> : null}
              </li>
            ))}
          </ul>
          <div className={styles.inline}>
            <iframe title="Before" src={out.before} className={styles.proof} />
            <iframe title="After" src={out.after} className={styles.proof} />
          </div>
        </>
      ) : visual ? (
        <div className={styles.stack} data-testid="rd-visual">
          <p className={styles.small}>
            {visual.same ? "The pages look the same." : <>New in the draft is <strong className={styles.newMark}>green</strong>; gone from the published print is <strong className={styles.goneMark}>red</strong>.</>}
            {" "}{visual.page_counts.published} → {visual.page_counts.draft} pages.{visual.truncated ? " Only the first pages are shown." : ""}
          </p>
          <label className={styles.small}>
            <input type="checkbox" checked={sideBySide} onChange={(e) => setSideBySide(e.target.checked)} /> Show before and after side by side
          </label>
          {visual.pages.map((p) => (
            <figure key={p.page} className={`${styles.stack} ${styles.figure}`}>
              <figcaption className={styles.small}>
                {p.summary}
                {p.only_in === "draft" ? " (new page)" : p.only_in === "published" ? " (no longer printed)" : ""}
              </figcaption>
              {sideBySide ? (
                <div className={styles.inline}>
                  {/* eslint-disable-next-line @next/next/no-img-element -- inline page picture (data URL) */}
                  <img alt={`Page ${p.page} before`} src={`data:image/png;base64,${p.before_png}`} className={styles.pageImg} />
                  {/* eslint-disable-next-line @next/next/no-img-element -- inline page picture (data URL) */}
                  <img alt={`Page ${p.page} after`} src={`data:image/png;base64,${p.after_png}`} className={styles.pageImg} />
                </div>
              ) : (
                // eslint-disable-next-line @next/next/no-img-element -- inline page picture (data URL)
                <img alt={`Page ${p.page} with changes highlighted`} src={`data:image/png;base64,${p.overlay_png}`} className={styles.pageImgWide} />
              )}
            </figure>
          ))}
        </div>
      ) : loading ? (
        <p className={styles.small}>Making page pictures…</p>
      ) : null}
      <Button size="sm" variant="ghost" onClick={onClose}>Close comparison</Button>
    </div>
  );
}

function BrandBox({ connectionId }: { connectionId: string }) {
  const [open, setOpen] = useState(false);
  const [opts, setOpts] = useState<Awaited<ReturnType<typeof api.brandOptions>> | null>(null);
  const [colour, setColour] = useState("");
  const [font, setFont] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [last, setLast] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const values = () => ({ ...(colour ? { primary_color: colour } : {}), ...(font ? { font } : {}) });
  const show = async () => {
    try {
      if (!opts) {
        const o = await api.brandOptions(connectionId);
        setOpts(o);
        setColour(String(o.company.primary_color ?? ""));
        setFont(String(o.company.font ?? ""));
      }
      setOpen(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't load branding.");
    }
  };
  if (!open) return <Button size="sm" variant="ghost" onClick={() => void show()}>Company branding…</Button>;
  return (
    <div className={styles.stack} data-testid="rd-brand">
      <h2 className={styles.title}>Branding for {String(opts?.company.name ?? "the company")}</h2>
      <p className={styles.small}>Applied once, to every document that uses the company layout.</p>
      <label className={styles.inline}>
        <span className={styles.small}>Main colour</span>
        <input type="color" aria-label="Main colour" value={/^#[0-9a-fA-F]{6}$/.test(colour) ? colour : "#714b67"} onChange={(e) => setColour(e.target.value)} />
      </label>
      <label className={styles.inline}>
        <span className={styles.small}>Font</span>
        <select aria-label="Font" value={font} onChange={(e) => setFont(e.target.value)}>
          {(opts?.fonts ?? []).map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
      </label>
      <div className={styles.inline}>
        <Button size="sm" variant="ghost" onClick={async () => { try { setPreview((await api.brandPreview(connectionId, values())).html); } catch (e) { toast.error(e instanceof Error ? e.message : "No preview."); } }}>Preview</Button>
        <Button size="sm" variant="primary" loading={busy} onClick={async () => {
          setBusy(true);
          try {
            const out = await api.brandApply(connectionId, values());
            setLast(out.previous as Record<string, unknown>);
            toast.success("Branding applied to the company.");
          } catch (e) {
            noteWriteRefusal(e);
            toast.error(e instanceof Error ? e.message : "Couldn't apply.");
          } finally {
            setBusy(false);
          }
        }}>Apply to the company</Button>
        {last ? <Button size="sm" variant="ghost" onClick={async () => { await api.brandUndo(connectionId, last); setLast(null); toast.success("Branding put back."); }}>Undo</Button> : null}
        <Button size="sm" variant="ghost" onClick={() => { setOpen(false); setPreview(null); }}>Close</Button>
      </div>
      {preview ? <iframe title="Branding preview" srcDoc={preview} sandbox="" className={styles.proof} /> : null}
    </div>
  );
}

function PageNumbers({ connectionId, companyId }: { connectionId: string; companyId: number | null }) {
  const [info, setInfo] = useState<{ stock_shows_numbers: boolean; ingenium_added: boolean; message: string } | null>(null);
  const check = () => api.pageNumbersCheck(connectionId, companyId).then(setInfo).catch((e) => toast.error(e instanceof Error ? e.message : "Couldn't check page numbers."));
  return (
    <div className={styles.stack} data-testid="rd-page-numbers">
      <Button size="sm" variant="ghost" onClick={() => void check()}>Page numbers…</Button>
      {info ? (
        <>
          <p className={styles.small}>{info.message}</p>
          {!info.stock_shows_numbers && !info.ingenium_added ? (
            <Button size="sm" variant="ghost" onClick={async () => { await api.pageNumbersSet(connectionId, true, companyId); void check(); }}>Add page numbers to the footer</Button>
          ) : null}
          {info.ingenium_added ? (
            <Button size="sm" variant="ghost" onClick={async () => { await api.pageNumbersSet(connectionId, false, companyId); void check(); }}>Turn page numbers off</Button>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
