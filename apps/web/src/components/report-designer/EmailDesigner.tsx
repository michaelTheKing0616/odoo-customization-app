"use client";

import { MailClientFrames } from "./MailClientFrames";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import type { BlockType, EmailLoadOut, EmailPreviewOut, EmailTemplateRow, Placement } from "@/lib/api/view-engine-2b";
import { addBlock, blockCount, newBlock } from "@/lib/viewDesigner2b";
import { blockReady, PlacementsEditor, type BlockContext, type FieldOpt } from "./BlockEditor";
import { AIEditBox, type AIMark } from "./AIEditBox";
import { BlockSets } from "./BlockSets";
import { EmailAppChecks } from "./Report2c";
import { Note } from "../view-designer/Note";
import styles from "./ReportDesigner.module.css";
import { Term } from "@/components/ui/Term";

const LABEL: Partial<Record<BlockType, string>> = { heading: "Heading", text: "Text", field: "Field value", label_field: "Label and value", divider: "Divider", spacer: "Space", line_table: "Lines table", image_field: "Picture" };
const msg = (err: unknown, fallback: string) => (err instanceof Error && err.message ? err.message : fallback);

/** Email designer: Odoo's template is never edited; blocks go on an Ingenium copy, previewed by Odoo's composer. */
export function EmailDesigner({ connectionId, model: initialModel }: { connectionId: string; model: string }) {
  const [model, setModel] = useState(initialModel);
  const [modelDraft, setModelDraft] = useState(initialModel);
  const [templates, setTemplates] = useState<EmailTemplateRow[] | null>(null);
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [loaded, setLoaded] = useState<EmailLoadOut | null>(null);
  const [placements, setPlacements] = useState<Placement[]>([]);
  const [aiMarks, setAiMarks] = useState<{ key: string; marks: AIMark[] } | null>(null);
  const [saved, setSaved] = useState<Placement[]>([]);
  const [slot, setSlot] = useState("bottom");
  const [recordId, setRecordId] = useState<number | null>(null);
  const [preview, setPreview] = useState<EmailPreviewOut | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [sending, setSending] = useState(false);
  const [sentNote, setSentNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);

  const list = useCallback(
    () => api.emailList(connectionId, model).then((o) => setTemplates(o.templates)).catch((e) => { setTemplates([]); toast.error(msg(e, "Couldn't list email templates.")); }),
    [connectionId, model],
  );
  useEffect(() => {
    void list();
  }, [list]);

  const open = useCallback(async (id: number) => {
    setTemplateId(id);
    setPreview(null);
    try {
      const out = await api.emailLoad(connectionId, id);
      setLoaded(out);
      setPlacements(out.placements ?? []);
      setSaved(out.placements ?? []);
      setRecordId(out.records[0]?.id ?? null);
    } catch (e) {
      setLoaded(null);
      toast.error(msg(e, "Couldn't open this email."));
    }
  }, [connectionId]);

  const key = JSON.stringify(placements);
  const ready = placements.every((p) => p.blocks.every(blockReady));
  useEffect(() => {
    if (!templateId || !recordId || !loaded || !ready) return;
    const t = window.setTimeout(async () => {
      abort.current?.abort();
      const ctl = new AbortController();
      abort.current = ctl;
      setPreviewing(true);
      try {
        const highlight = aiMarks && aiMarks.key === JSON.stringify(placements) ? aiMarks.marks : null;
        const out = await api.emailPreview(connectionId, { template_id: templateId, record_id: recordId, placements, highlight }, ctl.signal);
        if (!ctl.signal.aborted) setPreview(out);
      } catch (e) {
        if (!ctl.signal.aborted) toast.error(msg(e, "Odoo couldn't show this email."));
      } finally {
        if (abort.current === ctl) {
          abort.current = null;
          setPreviewing(false);
        }
      }
    }, 900);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, aiMarks, templateId, recordId, loaded, ready, connectionId]);
  useEffect(() => () => abort.current?.abort(), []);

  const fields: FieldOpt[] = useMemo(
    () =>
      Object.entries(loaded?.fields ?? {})
        .map(([name, f]) => ({ name, label: f.string || name, type: f.type ?? "" }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    [loaded],
  );
  const ctx: BlockContext = {
    fields,
    lineFields: loaded?.line_fields ?? [],
    loadColumns: async (field) => (await api.emailLinesFields(connectionId, templateId ?? 0, field)).columns,
  };
  const row = templates?.find((t) => t.id === templateId) ?? null;
  const dirty = key !== JSON.stringify(saved);

  return (
    <>
      <aside className={styles.left} aria-label="Email templates">
        <div className={styles.panel}>
          <form className={styles.inline} onSubmit={(e) => { e.preventDefault(); setModel(modelDraft.trim()); setTemplateId(null); setLoaded(null); }}>
            <Input aria-label="Record type for emails" value={modelDraft} onChange={(e) => setModelDraft(e.target.value)} spellCheck={false} />
            <Button size="sm" type="submit">Show</Button>
          </form>
          <h2 className={styles.title}><Term tech="mail.template">Email templates</Term></h2>
          {templates === null ? <p className={styles.small}>Reading <Term tech="mail.template">email templates</Term>…</p> : null}
          {templates?.length === 0 ? <p className={styles.small}>No <Term tech="mail.template">email templates</Term> for this <Term tech="ir.model">record type</Term>.</p> : null}
          <ul className={styles.blocks} data-testid="em-templates">
            {(templates ?? []).map((t) => (
              <li key={t.id}>
                <Button size="sm" variant="ghost" aria-pressed={t.id === templateId} onClick={() => void open(t.id)}>
                  {t.name}{t.ingenium_copy ? ", your copy" : ""}
                </Button>
              </li>
            ))}
          </ul>
          {loaded?.editable ? (
            <>
              <h2 className={styles.title}>Where</h2>
              {loaded.slots.map((sl) => (
                <label key={sl.id} className={styles.inline}>
                  <input type="radio" name="em-slot" checked={slot === sl.id} onChange={() => setSlot(sl.id)} />
                  {sl.label}
                </label>
              ))}
              <h2 className={styles.title}>Add</h2>
              <div className={styles.stack}>
                {loaded.blocks.map((t) => (
                  <Button key={t} size="sm" variant="ghost" onClick={() => setPlacements(addBlock(placements, slot, newBlock(t, fields.find((f) => f.type === "char")?.name ?? "name")))}>
                    {LABEL[t] ?? t}
                  </Button>
                ))}
              </div>
              <BlockSets connectionId={connectionId} model={model} placements={placements} email onUse={(p) => setPlacements([...placements, ...p])} />
              <AIEditBox what="email" placements={placements} onPlacements={setPlacements} onChanged={(marks, p) => setAiMarks({ key: JSON.stringify(p), marks })}
                propose={(text, p) => api.emailAiEdit(connectionId, { template_id: templateId ?? 0, text, placements: p })}
                apply={(p, ops) => api.emailAiApply(connectionId, { template_id: templateId ?? 0, placements: p, ops })} />
            </>
          ) : null}
        </div>
      </aside>

      <main className={styles.paperDesk} aria-label="Email">
        {!loaded ? <p className={styles.small}>Pick an <Term tech="mail.template">email template</Term> on the left.</p> : null}
        {loaded && !loaded.editable ? (
          <Note tone="warning" as="div" data-testid="em-copy-first">
            <p>This is Odoo&apos;s own template, so it isn&apos;t changed. Make a copy to add your blocks; the copy can then be chosen when sending.</p>
            <Button size="sm" variant="primary" loading={busy} onClick={async () => {
              setBusy(true);
              try {
                const out = await api.emailCopy(connectionId, loaded.template.id);
                await list();
                await open(out.template_id);
                toast.success("Copy made. Odoo's template is unchanged.");
              } catch (e) {
                toast.error(msg(e, "Couldn't make a copy."));
              } finally {
                setBusy(false);
              }
            }}>Make a copy</Button>
          </Note>
        ) : null}
        {loaded ? (
          <div className={styles.inline}>
            <span className={styles.small}>Preview with</span>
            <select aria-label="Preview record" value={recordId ?? ""} onChange={(e) => setRecordId(Number(e.target.value) || null)}>
              {loaded.records.map((r) => <option key={r.id} value={r.id}>{r.display_name}</option>)}
            </select>
          </div>
        ) : null}
        {loaded?.editable ? (
          <div className={styles.paper} data-testid="em-paper">
            <PlacementsEditor slots={loaded.slots} placements={placements} activeSlot={slot} onActiveSlot={setSlot} onChange={setPlacements} ctx={ctx} stockLabel="The email's own text" />
            <div className={styles.inline}>
              <Button size="sm" variant="primary" loading={busy} disabled={!dirty || !ready || !recordId || !blockCount(placements)} data-testid="em-save" onClick={async () => {
                if (!templateId || !recordId) return;
                setBusy(true);
                try {
                  const out = await api.emailSave(connectionId, { template_id: templateId, record_id: recordId, placements });
                  setSaved(placements);
                  setPreview(out);
                  toast.success("Email saved", { duration: 10000, action: { label: "Undo", onClick: () => void api.emailRestore(connectionId, templateId).then(() => open(templateId)) } });
                } catch (e) {
                  toast.error(msg(e, "Couldn't save."));
                } finally {
                  setBusy(false);
                }
              }}>Save email</Button>
              {row?.ingenium_copy ? (
                <Button size="sm" variant="ghost" onClick={async () => {
                  if (!templateId || !window.confirm("Delete this copy? Odoo's own template stays.")) return;
                  try {
                    await api.emailDelete(connectionId, templateId);
                    setTemplateId(null);
                    setLoaded(null);
                    await list();
                  } catch (e) {
                    toast.error(msg(e, "Couldn't delete."));
                  }
                }}>Delete this copy</Button>
              ) : null}
            </div>
          </div>
        ) : null}
      </main>

      <aside className={styles.right} aria-label="Email preview">
        <h2 className={styles.title}>As Odoo will send it</h2>
        {previewing ? <Note tone="busy" role="status">Updating the email preview…</Note> : null}
        {preview ? (
          <div className={styles.stack} data-testid="em-preview">
            <p className={styles.small}>Subject: {preview.subject}</p>
            <MailClientFrames html={preview.html} subject={preview.subject} widths={preview.widths} />
            <div className={styles.row}>
              <Button size="sm" variant="secondary" disabled={sending || !templateId || !recordId} data-testid="em-test-send" onClick={async () => {
                if (!templateId || !recordId) return;
                setSending(true); setSentNote(null);
                try { const r = await api.emailSendMeTest(connectionId, { template_id: templateId, record_id: recordId, placements }); setSentNote(`Sent a test to ${r.sent_to}. Only you get it.`); }
                catch (e) { setSentNote(e instanceof Error ? e.message : "Couldn't send the test."); }
                finally { setSending(false); }
              }}>Send me a test</Button>
              {sentNote ? <span className={styles.small} role="status">{sentNote}</span> : null}
            </div>
          </div>
        ) : null}
        {templateId ? (
          <EmailAppChecks connectionId={connectionId} templateId={templateId} recordId={recordId} html={preview?.html ?? null} />
        ) : (
          <p className={styles.small}>Nothing is sent. Odoo&apos;s composer writes the preview for the chosen record.</p>
        )}
      </aside>
    </>
  );
}
