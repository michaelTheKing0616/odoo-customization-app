"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import type { EngineOp, EngineRecord, EngineViewType } from "@/lib/api/view-engine";
import type { Change2d, Comment2d, Compare2d, Outline2d, TileOut, TileSpec } from "@/lib/api/view-engine-2d";
import { errorDetail } from "@/lib/viewDesigner2b";
import { Note } from "../view-designer/Note";
import styles from "./ViewDesigner.module.css";

export type P2d = {
  connectionId: string;
  model: string;
  viewType: EngineViewType;
  viewId: number | null;
  fields: Record<string, { string?: string; type?: string }>;
  selectedNode?: string | null;
  onAddOps?: (ops: EngineOp[], label: string) => void;
  onSample: (rec: EngineRecord | null) => void;
  onChanged: () => void;
  errorText: (err: unknown) => string;
};

const scr = (p: P2d) => ({ model: p.model, view_type: p.viewType, view_id: p.viewId });

function useRun(errorText: (e: unknown) => string) {
  const [busy, setBusy] = useState<string | null>(null);
  const run = async <T,>(key: string, fn: () => Promise<T>, done: (v: T) => void) => {
    setBusy(key);
    try {
      done(await fn());
    } catch (err) {
      toast.error(errorText(err));
    } finally {
      setBusy(null);
    }
  };
  return { busy, run };
}

/** Insights extras: hide unused fields, accessibility fixes, industry samples, printable guide, comments. */
export function Insights2d(p: P2d) {
  const { busy, run } = useRun(p.errorText);
  const [industries, setIndustries] = useState<string[]>([]);
  const [lang, setLang] = useState("en");
  const [comments, setComments] = useState<Comment2d[]>([]);
  const [text, setText] = useState("");
  const loadComments = () => api.comments(p.connectionId, scr(p)).then((o) => setComments(o.comments)).catch(() => undefined);
  useEffect(() => {
    api.industries(p.connectionId).then((o) => setIndustries(o.industries)).catch(() => undefined);
    void loadComments();
  }, [p.connectionId, p.model, p.viewType, p.viewId]); // eslint-disable-line react-hooks/exhaustive-deps
  const addOps = (ops: EngineOp[], label: string, none: string) => {
    if (!ops.length) return toast(none);
    p.onAddOps?.(ops, label);
    toast.success(`${label}. Check the draft, then publish.`);
  };
  return (
    <div className={styles.stack} data-testid="vd2d-insights">
      <h3 className={styles.sectionTitle}>Tidy up</h3>
      <div className={styles.row}>
        <Button size="sm" variant="ghost" disabled={busy === "unused"}
          onClick={() => void run("unused", () => api.hideUnused(p.connectionId, scr(p)), (o) => (o.ops.length ? addOps(o.ops, `Hide ${o.ops.length} unused field${o.ops.length === 1 ? "" : "s"}`, o.note) : toast(o.note)))}>
          Hide fields nobody fills in
        </Button>
        <Button size="sm" variant="ghost" disabled={busy === "a11y"}
          onClick={() => void run("a11y", () => api.a11yFix(p.connectionId, scr(p)), (o) => addOps(o.ops, `${o.ops.length} accessibility fix${o.ops.length === 1 ? "" : "es"}`, o.note))}>
          Fix accessibility
        </Button>
      </div>
      <h3 className={styles.sectionTitle}>Sample data by industry</h3>
      <select className={styles.select} aria-label="Industry" defaultValue=""
        onChange={(e) => e.target.value && void run("ind", () => api.industrySample(p.connectionId, scr(p), e.target.value), (o) => p.onSample((o.records[0] ?? null) as unknown as EngineRecord))}>
        <option value="">Pick an industry…</option>
        {industries.map((i) => <option key={i} value={i}>{i}</option>)}
      </select>
      <p className={styles.muted}>Sample values are made up and labelled &quot;Sample:&quot;. Nothing is saved.</p>
      <h3 className={styles.sectionTitle}>Printable guide</h3>
      <div className={styles.row}>
        <select className={styles.select} aria-label="Language" value={lang} onChange={(e) => setLang(e.target.value)}>
          {[["en", "English"], ["fr", "French"], ["es", "Spanish"], ["de", "German"], ["pt", "Portuguese"], ["yo", "Yoruba"], ["ha", "Hausa"], ["ig", "Igbo"]].map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <Button size="sm" variant="ghost" disabled={busy === "pdf"}
          onClick={() => void run("pdf", () => api.explainExport(p.connectionId, scr(p), lang), ({ blob, pdf }) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = pdf ? "screen-guide.pdf" : "screen-guide.html";
            a.click();
            URL.revokeObjectURL(url);
          })}>
          Download guide
        </Button>
      </div>
      <h3 className={styles.sectionTitle}>Comments{comments.length ? ` (${comments.length})` : ""}</h3>
      <ul className={styles.list}>
        {comments.map((c) => (
          <li key={c.id} className={styles.listItem}>
            <span>{c.payload.text} <span className={styles.muted}>{c.payload.by}</span></span>
            <Button size="sm" variant="ghost" onClick={() => void run("res", () => api.commentResolve(p.connectionId, c.id), () => void loadComments())}>Resolve</Button>
          </li>
        ))}
      </ul>
      <div className={styles.row}>
        <Input aria-label="Comment" placeholder={p.selectedNode ? "Comment on the selected item" : "Select an item to comment on it"} value={text} onChange={(e) => setText(e.target.value)} />
        <Button size="sm" variant="ghost" disabled={!text.trim() || !p.selectedNode}
          onClick={() => void run("com", () => api.commentAdd(p.connectionId, scr(p), p.selectedNode as string, text.trim()), () => { setText(""); void loadComments(); })}>
          Add
        </Button>
      </div>
    </div>
  );
}

/** Dashboards extras: number tiles comparing this period with the last one. */
export function Tiles2d(p: P2d) {
  const { busy, run } = useRun(p.errorText);
  const dates = Object.entries(p.fields).filter(([, m]) => m.type === "date" || m.type === "datetime");
  const nums = Object.entries(p.fields).filter(([, m]) => m.type === "float" || m.type === "monetary" || m.type === "integer");
  const [spec, setSpec] = useState<TileSpec>({ model: p.model, measure: "__count", date_field: dates[0]?.[0] ?? "", period: "month" });
  const [tiles, setTiles] = useState<TileOut[]>([]);
  const [preview, setPreview] = useState<TileOut | null>(null);
  const load = () => api.tiles(p.connectionId).then((o) => setTiles(o.tiles)).catch(() => undefined);
  useEffect(() => { void load(); }, [p.connectionId]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className={styles.stack} data-testid="vd2d-tiles">
      <h3 className={styles.sectionTitle}>Number tiles</h3>
      <div className={styles.row}>
        <select className={styles.select} aria-label="Number" value={spec.measure} onChange={(e) => setSpec({ ...spec, measure: e.target.value })}>
          <option value="__count">How many</option>
          {nums.map(([k, m]) => <option key={k} value={k}>{m.string ?? k}</option>)}
        </select>
        <select className={styles.select} aria-label="Date" value={spec.date_field} onChange={(e) => setSpec({ ...spec, date_field: e.target.value })}>
          {dates.map(([k, m]) => <option key={k} value={k}>{m.string ?? k}</option>)}
        </select>
        <select className={styles.select} aria-label="Period" value={spec.period} onChange={(e) => setSpec({ ...spec, period: e.target.value as TileSpec["period"] })}>
          <option value="week">This week</option><option value="month">This month</option><option value="quarter">This quarter</option>
        </select>
      </div>
      <div className={styles.row}>
        <Button size="sm" variant="ghost" disabled={!spec.date_field || busy === "pv"} onClick={() => void run("pv", () => api.tilePreview(p.connectionId, { ...spec, model: p.model }), setPreview)}>Preview</Button>
        <Button size="sm" variant="primary" disabled={!spec.date_field || busy === "sv"} onClick={() => void run("sv", () => api.tileSave(p.connectionId, { ...spec, model: p.model }), () => void load())}>Add tile</Button>
      </div>
      {preview ? <p data-testid="vd2d-tile-preview">{preview.label}: <strong>{preview.value}</strong>. {preview.change}</p> : null}
      <ul className={styles.list}>
        {tiles.map((t) => (
          <li key={t.id} className={styles.listItem}>
            <span>{t.label}: {t.error ?? <><strong>{t.value}</strong> <span className={styles.muted}>{t.change}</span></>}</span>
            <Button size="sm" variant="ghost" onClick={() => t.id && void run("del", () => api.tileDelete(p.connectionId, t.id as string), () => void load())}>Remove</Button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Publishing extras: what changed, named approvers, pause window, checklist, chat digest, move to another database. */
export function Publishing2d(p: P2d) {
  const { busy, run } = useRun(p.errorText);
  const [approvalIds, setApprovalIds] = useState<string[]>([]);
  const [diff, setDiff] = useState<Record<string, Change2d[]>>({});
  const [approvers, setApprovers] = useState("");
  const [pauseNote, setPauseNote] = useState<string | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [hook, setHook] = useState("");
  const [target, setTarget] = useState("");
  const [others, setOthers] = useState<{ id: string; name: string }[]>([]);
  const [cmp, setCmp] = useState<Compare2d | null>(null);
  const [needsOk, setNeedsOk] = useState(false);
  const [replace, setReplace] = useState(false);
  useEffect(() => {
    api.listConnections().then((cs) => setOthers(cs.filter((c) => c.id !== p.connectionId).map((c) => ({ id: c.id, name: c.name })))).catch(() => undefined);
  }, [p.connectionId]);
  const showChecklist = async () => {
    try {
      const o = await api.checklistPublish(p.connectionId, scr(p));
      toast.success(`Checklist live with ${o.lines} line${o.lines === 1 ? "" : "s"}`, { description: o.role_layouts?.join(" ") });
      p.onChanged();
    } catch (err) {
      setNeedsOk(Boolean(errorDetail(err)?.needs_approval));
      toast.error(p.errorText(err));
    }
  };
  useEffect(() => {
    api.approvers(p.connectionId).then((o) => setApprovers((o.approvers[p.model] ?? []).join(", "))).catch(() => undefined);
    api.pauses(p.connectionId).then((o) => setPauseNote(o.note)).catch(() => undefined);
    api.approvals(p.connectionId, p.model).then((o) => setApprovalIds(o.approvals.filter((a) => a.payload.status === "pending").map((a) => a.id))).catch(() => undefined);
  }, [p.connectionId, p.model]);
  const iso = (v: string) => (v ? new Date(v).toISOString() : "");
  return (
    <div className={styles.stack} data-testid="vd2d-publishing">
      {approvalIds.length ? <h3 className={styles.sectionTitle}>What each request changes</h3> : null}
      {approvalIds.map((id) => (
        <div key={id} className={styles.stack}>
          <Button size="sm" variant="ghost" onClick={() => void run(`d${id}`, () => api.approvalDiff(p.connectionId, id), (o) => setDiff((d) => ({ ...d, [id]: o.changes })))}>Show what changes</Button>
          {diff[id] ? <ul className={styles.list}>{diff[id].map((c, i) => <li key={i} className={styles.listItem} data-kind={c.kind}>{c.text}</li>)}</ul> : null}
        </div>
      ))}
      <h3 className={styles.sectionTitle}>Who can approve {p.model}</h3>
      <div className={styles.row}>
        <Input aria-label="Approvers" placeholder="Email addresses, comma separated (empty = anyone else)" value={approvers} onChange={(e) => setApprovers(e.target.value)} />
        <Button size="sm" variant="ghost" onClick={() => void run("ap", async () => {
          const cur = (await api.approvers(p.connectionId)).approvers;
          const list = approvers.split(",").map((x) => x.trim()).filter(Boolean);
          return api.setApprovers(p.connectionId, { ...cur, [p.model]: list });
        }, () => toast.success("Approvers saved"))}>Save</Button>
      </div>
      <h3 className={styles.sectionTitle}>Pause scheduled publishing</h3>
      {pauseNote ? <Note tone="info" role="status">{pauseNote}</Note> : null}
      <div className={styles.row}>
        <Input type="datetime-local" aria-label="Pause from" value={start} onChange={(e) => setStart(e.target.value)} />
        <Input type="datetime-local" aria-label="Pause until" value={end} onChange={(e) => setEnd(e.target.value)} />
        <Button size="sm" variant="ghost" disabled={!start || !end} onClick={() => void run("pz", () => api.pauseSet(p.connectionId, iso(start), iso(end), "Odoo upgrade"), () => toast.success("Scheduled changes will wait during that time"))}>Pause</Button>
      </div>
      <h3 className={styles.sectionTitle}>Stage checklist on the record</h3>
      <div className={styles.row}>
        <Button size="sm" variant="ghost" disabled={busy === "cl"} onClick={() => void run("cl", showChecklist, () => undefined)}>Show checklist</Button>
        {needsOk ? (
          <Button size="sm" variant="ghost" onClick={() => void run("clok", () => api.requestAction(p.connectionId, "checklist_publish", scr(p), [`Stage checklist on ${p.model}`]), () => { setNeedsOk(false); toast.success("Sent for approval"); })}>Ask for approval</Button>
        ) : null}
        <Button size="sm" variant="ghost" onClick={() => void run("clr", () => api.checklistRemove(p.connectionId, scr(p)), () => { toast.success("Checklist removed"); p.onChanged(); })}>Remove</Button>
      </div>
      <h3 className={styles.sectionTitle}>Weekly digest to Slack or Teams</h3>
      <div className={styles.row}>
        <Input aria-label="Webhook link" placeholder="Slack, Teams or Teams Workflows (Power Automate) link" value={hook} onChange={(e) => setHook(e.target.value)} />
        <Button size="sm" variant="ghost" disabled={!hook} onClick={() => void run("hk", () => api.digestChat(p.connectionId, hook), (o) => { setHook(""); toast.success(`Digest goes to ${o.kind} (${o.url})`); })}>Save</Button>
        <Button size="sm" variant="ghost" disabled={busy === "hkt"} onClick={() => void run("hkt", () => api.digestChatSend(p.connectionId), (o) => toast.success(`${o.note} (${o.sent_to})`))}>Send a test</Button>
      </div>
      <h3 className={styles.sectionTitle}>Move this screen to another database</h3>
      <div className={styles.row}>
        <select aria-label="Target database" className={styles.select} value={target} onChange={(e) => { setTarget(e.target.value); setCmp(null); setReplace(false); }}>
          <option value="">Choose a database…</option>
          {others.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <Button size="sm" variant="ghost" disabled={!target || busy === "cmp"} onClick={() => void run("cmp", () => api.promoteCompare(p.connectionId, scr(p), target), setCmp)}>Compare side by side</Button>
        <Button size="sm" variant="ghost" disabled={!target || Boolean(cmp?.problems.length) || (Boolean(cmp?.replaces) && !replace)} onClick={() => void run("pr", () => api.promote(p.connectionId, scr(p), target, replace), (o) => toast.success(o.note))}>Ask to move</Button>
      </div>
      {cmp?.replaces ? (
        <label className={styles.row}>
          <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} /> Replace the Ingenium changes that database already has on this screen
        </label>
      ) : null}
      {cmp ? <CompareView cmp={cmp} /> : null}
    </div>
  );
}

function OutlineCol({ title, items, marks, focus }: { title: string; items: Outline2d; marks?: Set<string>; focus?: string | null }) {
  return (
    <div className={styles.stack}>
      <h4 className={styles.sectionTitle}>{title}</h4>
      <ul className={styles.list}>
        {items.map((it) => (
          <li
            key={it.node}
            ref={focus === it.node ? (el) => el?.scrollIntoView?.({ block: "nearest" }) : undefined}
            className={styles.listItem}
            data-kind={marks?.has(it.node) ? "changed" : undefined}
            data-hidden={it.hidden || undefined}
            data-focus={focus === it.node || undefined}
            aria-current={focus === it.node ? "true" : undefined}
          >
            {it.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Side by side: this database, the other database now, and the other database after the move. */
const KIND_WORD: Record<string, string> = { added: "Only there", removed: "Only here", changed: "Set differently", moved: "Order" };

/** Step through what will still look different after the move, one item at a time (stage 4 idea 1). */
export function DiffStepper({ items, at, onAt }: { items: Change2d[]; at: number | null; onAt: (i: number | null) => void }) {
  if (!items.length) return null;
  if (at === null) {
    return (
      <p className={styles.row}>
        <span className={styles.muted}>{items.length} item{items.length === 1 ? "" : "s"} will still look different there (different Odoo version or add-ons).</span>
        <Button size="sm" variant="ghost" onClick={() => onAt(0)} data-testid="vd2e-diff-open">Go through them</Button>
      </p>
    );
  }
  const d = items[at];
  return (
    <div className={styles.row} role="group" aria-label="Remaining differences" data-testid="vd2e-diff-step">
      <Button size="sm" variant="ghost" disabled={at === 0} onClick={() => onAt(at - 1)}>Previous</Button>
      <p role="status" aria-live="polite">Difference {at + 1} of {items.length}: <strong>{KIND_WORD[d.kind] ?? d.kind}</strong>, {d.text.replace(/^(Only there|Not there): /, "")}</p>
      <Button size="sm" variant="ghost" disabled={at === items.length - 1} onClick={() => onAt(at + 1)}>Next</Button>
      <Button size="sm" variant="ghost" onClick={() => onAt(null)}>Done</Button>
    </div>
  );
}

export function CompareView({ cmp }: { cmp: Compare2d }) {
  const marks = new Set(cmp.changes.map((c) => c.node));
  const [at, setAt] = useState<number | null>(null);
  const cur = at === null ? null : cmp.still_different[at];
  const focusHere = cur && cur.kind === "removed" ? cur.node : null;
  const focusThere = cur && cur.kind !== "removed" ? cur.node || null : null;
  return (
    <div className={styles.stack} data-testid="vd2e-compare">
      {cmp.problems.length ? <ul className={styles.list}>{cmp.problems.map((t, i) => <li key={i} role="alert" className={styles.listItem}>{t}</li>)}</ul> : null}
      <Note tone="info" role="status">{cmp.changes.length ? `${cmp.changes.length} change${cmp.changes.length === 1 ? "" : "s"} there.` : "Nothing would change there."} {cmp.note}</Note>
      <div className={styles.compareGrid}>
        <OutlineCol title={`Here (Odoo ${cmp.source.major})`} items={cmp.source.items} focus={focusHere} />
        <OutlineCol title={`There now (Odoo ${cmp.target_now.major})`} items={cmp.target_now.items} />
        <OutlineCol title="There after the move" items={cmp.target_after.items} marks={marks} focus={focusThere} />
      </div>
      <DiffStepper items={cmp.still_different} at={at} onAt={setAt} />
    </div>
  );
}
