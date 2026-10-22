"use client";

import { pushRecent } from "@/lib/recentRecords";
import { flushSync } from "react-dom";
import { morphInPlace } from "@/lib/morph";
import { RecordBoard, pickBoardField } from "./RecordBoard";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Search, X } from "@/components/ui/icons";
import { recordsApi, type RecEdit, type RecField, type RecMeta, type RecRow, type RecSearch } from "@/lib/api/suite";
import { errText, useSuite } from "./SuiteContext";
import { PageHead, SafetyLevel, Status } from "./parts";
import styles from "./Suite.module.css";
import { Term } from "@/components/ui/Term";

const ROW_H = 32;
const OPS: { op: string; word: string }[] = [
  { op: "ilike", word: "contains" }, { op: "=", word: "is" }, { op: "!=", word: "is not" }, { op: ">", word: "more than" }, { op: "<", word: "less than" },
];

export function showValue(v: unknown, f?: RecField): string {
  if (v === false || v === null || v === undefined) return f?.type === "boolean" ? "No" : "";
  if (v === true) return "Yes";
  if (Array.isArray(v)) return v.length === 2 && typeof v[0] === "number" && typeof v[1] === "string" ? v[1] : `${v.length} linked`;
  if (f?.choices.length) return f.choices.find((c) => c.value === v)?.label ?? String(v);
  if (f?.type === "html") return String(v).replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  return String(v);
}

/** Parse pasted spreadsheet rows. Header row: first column is the record number (id, ID or #), others name fields by label or name. */
export function parsePaste(text: string, fields: RecField[]): { edits: RecEdit[]; problems: string[] } {
  const lines = text.replace(/\r\n/g, "\n").split("\n").filter((l) => l.trim());
  if (lines.length < 2) return { edits: [], problems: ["Paste a header row and at least one row."] };
  const sep = lines[0].includes("\t") ? "\t" : lines[0].includes(";") ? ";" : ",";
  const head = lines[0].split(sep).map((h) => h.trim());
  if (!/^(id|#|record|record number)$/i.test(head[0])) return { edits: [], problems: ["The first column must be the record number (call it id or #)."] };
  const byKey = new Map<string, RecField>();
  for (const f of fields) { byKey.set(f.name.toLowerCase(), f); byKey.set(f.label.toLowerCase(), f); }
  const cols = head.slice(1).map((h) => byKey.get(h.toLowerCase()));
  const problems = head.slice(1).filter((_, i) => !cols[i]).map((h) => `No field called '${h}' here.`)
    .concat(cols.filter((f): f is RecField => !!f && !f.editable).map((f) => `'${f.label}' can't be edited: ${f.why_not ?? ""}`));
  const edits: RecEdit[] = [];
  for (const line of lines.slice(1)) {
    const cells = line.split(sep);
    const id = parseInt(cells[0].replace(/^#/, ""), 10);
    if (!(id > 0)) { problems.push(`'${cells[0]}' is not a record number.`); continue; }
    cols.forEach((f, i) => { if (f && f.editable) edits.push({ id, field: f.name, value: (cells[i + 1] ?? "").trim() }); });
  }
  return { edits, problems };
}

function ValueInput({ f, value, onChange, label, autoFocus, onKeyDown }: { f: RecField; value: string; onChange: (v: string) => void; label: string; autoFocus?: boolean; onKeyDown?: (e: React.KeyboardEvent) => void }) {
  if (f.choices.length || f.type === "boolean") {
    const opts = f.type === "boolean" ? [{ value: "yes", label: "Yes" }, { value: "no", label: "No" }] : f.choices;
    return <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} autoFocus={autoFocus} onKeyDown={onKeyDown}><option value="">Empty</option>{opts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>;
  }
  return <input aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} autoFocus={autoFocus} onKeyDown={onKeyDown} placeholder={f.type === "many2one" ? "Exact name" : undefined} />;
}

/** Record editor (spec 6.8b): any record type as a sheet. Edits are staged, then become one checked plan. */
export function RecordEditor() {
  const { connectionId } = useSuite();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [models, setModels] = useState<{ model: string; label: string; view_only: string | null }[]>([]);
  const [model, setModel] = useState<string>("res.partner");
  const [meta, setMeta] = useState<RecMeta | null>(null);
  const [cols, setCols] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<[string, string, unknown][]>([]);
  const [groupBy, setGroupBy] = useState("");
  const [order, setOrder] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [limit, setLimit] = useState(80);
  const [archived, setArchived] = useState(false);
  const [data, setData] = useState<RecSearch | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [staged, setStaged] = useState<Map<string, RecEdit & { old: unknown }>>(new Map());
  const [editing, setEditing] = useState<{ id: number; field: string; value: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  // Touch 80: list or board; the selection is shared, so it survives the switch.
  const [view, setView] = useState<"list" | "board">("list");
  // Touch 35: a row opens into its record sheet (read-only; edits stay in the grid).
  const [sheetId, setSheetId] = useState<number | null>(null);
  // 143: opened from Find anything (?model=…&open=id): pick the model, narrow to that record, open its sheet.
  const [openFromUrl] = useState(() => {
    if (typeof window === "undefined") return null;
    const p = new URLSearchParams(window.location.search);
    const id = Number(p.get("open"));
    return p.get("model") && id ? { model: p.get("model")!, id } : null;
  });
  useEffect(() => {
    if (!openFromUrl) return;
    setModel(openFromUrl.model);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (openFromUrl && meta?.model === openFromUrl.model) { setFilters([["id", "=", openFromUrl.id]]); setSheetId(openFromUrl.id); }
  }, [meta, openFromUrl]);
  const [nf, setNf] = useState<{ field: string; op: string; value: string }>({ field: "", op: "ilike", value: "" });
  const [bulk, setBulk] = useState<{ field: string; value: string }>({ field: "", value: "" });
  const [fr, setFr] = useState<{ field: string; find: string; replace: string }>({ field: "", find: "", replace: "" });
  const [paste, setPaste] = useState("");
  const viewport = useRef<HTMLDivElement>(null);

  useEffect(() => { const h = setTimeout(() => { recordsApi.models(connectionId, q).then((r) => setModels(r.models), () => undefined); }, 200); return () => clearTimeout(h); }, [q, connectionId]);
  useEffect(() => {
    setMeta(null); setData(null); setSelected(new Set()); setStaged(new Map()); setFilters([]); setGroupBy(""); setPage(0); setOrder(null);
    recordsApi.meta(connectionId, model).then((m) => { setMeta(m); setCols(m.columns); }, (e: unknown) => setError(errText(e)));
  }, [model, connectionId]);
  const fmap = useMemo(() => new Map((meta?.fields ?? []).map((f) => [f.name, f])), [meta]);
  const boardField = useMemo(() => pickBoardField(meta?.fields ?? []), [meta]);
  const load = useCallback(() => {
    if (!meta) return;
    const fetchCols = view === "board" && boardField && !cols.includes(boardField.name) ? [...cols, boardField.name] : cols;
    recordsApi.search(connectionId, model, { search, filters, fields: fetchCols, group_by: groupBy || null, offset: page * limit, limit, order, archived })
      .then((d) => { setData(d); setError(null); }, (e: unknown) => setError(errText(e)));
  }, [meta, connectionId, model, search, filters, cols, groupBy, page, limit, order, archived, view, boardField]);
  useEffect(() => { const h = setTimeout(load, 150); return () => clearTimeout(h); }, [load]);

  const rows = data?.rows ?? [];
  const height = 420;
  const first = Math.max(0, Math.floor(scrollTop / ROW_H) - 5);
  const last = Math.min(rows.length, Math.ceil((scrollTop + height) / ROW_H) + 5);
  const editable = (f?: RecField) => !!f && f.editable && !meta?.view_only;

  function stage(edits: RecEdit[]) {
    setStaged((m) => {
      const n = new Map(m);
      for (const e of edits) {
        const row = rows.find((r) => r.id === e.id);
        const key = `${e.id}:${e.field}`;
        n.set(key, { ...e, old: n.get(key)?.old ?? row?.[e.field] });
      }
      return n;
    });
  }
  function toValue(f: RecField, v: string): unknown {
    if (f.type === "boolean") return v === "" ? false : v === "yes";
    if (f.type === "many2one") return v ? { ref: v } : false;
    return v;
  }
  function commitCell() {
    if (!editing) return;
    const f = fmap.get(editing.field)!;
    stage([{ id: editing.id, field: editing.field, value: toValue(f, editing.value) }]);
    setEditing(null);
  }
  async function act(name: string, fn: () => Promise<unknown>) {
    setBusy(name); setError(null);
    try { await fn(); } catch (e) { setError(errText(e)); } finally { setBusy(null); }
  }
  async function makePlan() {
    await act("plan", async () => {
      const out = await recordsApi.plan(connectionId, model, [...staged.values()].map(({ id, field, value }) => ({ id, field, value })), `Edit ${meta?.label ?? model}`);
      if (out.refused.length) setNotes(out.refused.map((r) => `#${r.id} ${r.field}: ${r.problem}`));
      router.push(`/connections/${connectionId}/suite/setup?plan=${out.plan.id}&view=board`);
    });
  }
  const pages = data ? Math.max(1, Math.ceil(data.total / limit)) : 1;
  const textFields = (meta?.fields ?? []).filter((f) => f.editable && (f.type === "char" || f.type === "text"));
  const editFields = (meta?.fields ?? []).filter((f) => f.editable);
  const allOnPage = rows.length > 0 && rows.every((r) => selected.has(r.id));

  return (
    <>
      <PageHead title="Record editor" purpose="Open any record type and edit it like a sheet. Edits are held here, then become one plan that is checked before anything is written." actions={<SafetyLevel level="undo" />} />
      <nav aria-label="Tools" className={styles.row}><Link href={`/connections/${connectionId}/suite/change/edit`}>Back to Change records</Link></nav>
      <div className={styles.row}>
        <label className={styles.row}><Search aria-hidden width={14} height={14} /> <Term tech="ir.model">Record type</Term>
          <input aria-label="Find a record type" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Contacts, Journal entries…" data-testid="rec-model-search" />
        </label>
        <select aria-label="Record type" value={model} onChange={(e) => setModel(e.target.value)} data-testid="rec-model">
          {!models.some((m) => m.model === model) ? <option value={model}>{meta?.label ?? model}</option> : null}
          {models.map((m) => <option key={m.model} value={m.model}>{m.label}{m.view_only ? " (view only)" : ""}</option>)}
        </select>
      </div>
      {error ? <Status tone="danger">{error}</Status> : null}
      {meta?.view_only ? <Status tone="warning" data-testid="rec-view-only">{meta.view_only}</Status> : null}
      {!meta ? <Status tone="busy">Reading…</Status> : (
        <>
          <div className={styles.row} aria-label="Find records">
            <input aria-label="Search" value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} placeholder="Search by name" data-testid="rec-search" />
            <select aria-label="Filter field" value={nf.field} onChange={(e) => setNf({ ...nf, field: e.target.value })}><option value="">Add a filter…</option>{meta.fields.filter((f) => f.stored).map((f) => <option key={f.name} value={f.name}>{f.label}</option>)}</select>
            {nf.field ? <>
              <select aria-label="Filter rule" value={nf.op} onChange={(e) => setNf({ ...nf, op: e.target.value })}>{OPS.map((o) => <option key={o.op} value={o.op}>{o.word}</option>)}</select>
              <input aria-label="Filter value" value={nf.value} onChange={(e) => setNf({ ...nf, value: e.target.value })} />
              <Button size="sm" variant="secondary" onClick={() => { const f = fmap.get(nf.field); const v = f?.type === "boolean" ? ["yes", "true"].includes(nf.value.toLowerCase()) : ["integer", "float", "monetary", "many2one"].includes(f?.type ?? "") && /^\d+(\.\d+)?$/.test(nf.value) ? Number(nf.value) : nf.value; setFilters((x) => [...x, [nf.field, nf.op, v]]); setNf({ field: "", op: "ilike", value: "" }); setPage(0); }}>Add</Button>
            </> : null}
            <label className={styles.row}>Group by
              <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)} data-testid="rec-group"><option value="">Nothing</option>{meta.fields.filter((f) => f.groupable).map((f) => <option key={f.name} value={f.name}>{f.label}</option>)}</select>
            </label>
            {meta.has_active ? <label className={styles.row}><input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} /> Include archived</label> : null}
            <details>
              <summary>Columns ({cols.length})</summary>
              <div className={styles.card} style={{ maxBlockSize: 240, overflow: "auto" }}>
                {meta.fields.filter((f) => f.type !== "binary").map((f) => <label key={f.name} className={styles.row}><input type="checkbox" checked={cols.includes(f.name)} onChange={(e) => setCols((c) => (e.target.checked ? [...c, f.name] : c.filter((x) => x !== f.name)))} /> {f.label}</label>)}
              </div>
            </details>
          </div>
          {filters.length ? <ul className={styles.row} aria-label="Filters">{filters.map((f, i) => (
            <li key={i} className={styles.tag}>{fmap.get(f[0])?.label ?? f[0]} {OPS.find((o) => o.op === f[1])?.word ?? f[1]} {String(f[2])}
              <button type="button" className={styles.linkBtn} aria-label="Remove filter" onClick={() => setFilters((x) => x.filter((_, j) => j !== i))}><X aria-hidden width={12} height={12} /></button></li>
          ))}</ul> : null}
          {data?.groups ? <ul className={styles.row} aria-label="Groups" data-testid="rec-groups">{data.groups.map((g, i) => (
            <li key={i}><button type="button" className={styles.linkBtn} onClick={() => { setFilters((x) => [...x, [groupBy, "=", g.value ?? false]]); setGroupBy(""); setPage(0); }}>{g.label} ({g.count})</button></li>
          ))}</ul> : null}
          {boardField ? (
            <div className={styles.row} role="group" aria-label="Layout" data-testid="rec-view-toggle">
              <Button size="sm" variant={view === "list" ? "primary" : "secondary"} aria-pressed={view === "list"} onClick={() => setView("list")}>List</Button>
              <Button size="sm" variant={view === "board" ? "primary" : "secondary"} aria-pressed={view === "board"} onClick={() => setView("board")}>{`Board by ${boardField.label}`}</Button>
            </div>
          ) : null}
          <p className={styles.mutedLine} data-testid="rec-total">{data ? `${data.total ? data.offset + 1 : 0} to ${data.offset + rows.length} of ${data.total}` : "Reading…"} · {selected.size} selected · {staged.size} edits held</p>
          {view === "board" && boardField ? (
            <RecordBoard rows={rows} field={boardField} selected={selected} onToggle={(id, on) => setSelected((s) => { const n = new Set(s); if (on) n.add(id); else n.delete(id); return n; })} />
          ) : (
          <div role="grid" aria-rowcount={rows.length + 1} aria-label={meta.label} className={styles.card} style={{ padding: 0 }}>
            <div role="row" className={styles.row} style={{ flexWrap: "nowrap", blockSize: ROW_H, borderBlockEnd: "1px solid var(--border-subtle)", paddingInline: 8 }}>
              <span role="columnheader" style={{ inlineSize: 28 }}><input type="checkbox" aria-label="Select all on this page" checked={allOnPage} onChange={(e) => setSelected((s) => { const n = new Set(s); rows.forEach((r) => (e.target.checked ? n.add(r.id) : n.delete(r.id))); return n; })} /></span>
              <span role="columnheader" style={{ inlineSize: 60 }} className={styles.muted}>#</span>
              {cols.map((c) => { const f = fmap.get(c); return (
                <span role="columnheader" key={c} style={{ flex: 1, minInlineSize: 120 }} aria-sort={order?.startsWith(`${c} `) ? (order.endsWith("desc") ? "descending" : "ascending") : "none"}>
                  {f?.sortable ? <button type="button" className={styles.linkBtn} onClick={() => setOrder((o) => (o === `${c} asc` ? `${c} desc` : `${c} asc`))}>{f.label}</button> : (f?.label ?? c)}
                </span>); })}
            </div>
            <div ref={viewport} style={{ blockSize: height, overflow: "auto", position: "relative" }} onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)} data-testid="rec-viewport">
              <div style={{ blockSize: rows.length * ROW_H, position: "relative" }}>
                {rows.slice(first, last).map((r: RecRow, k) => (
                  <div role="row" key={r.id} aria-rowindex={first + k + 2} aria-selected={selected.has(r.id)} className={styles.row} data-testid={`rec-row-${r.id}`}
                    style={{ position: "absolute", insetBlockStart: (first + k) * ROW_H, insetInline: 0, blockSize: ROW_H, flexWrap: "nowrap", paddingInline: 8, borderBlockEnd: "1px solid var(--border-subtle)" }}>
                    <span role="gridcell" style={{ inlineSize: 28 }}><input type="checkbox" aria-label={`Select ${r.display_name}`} checked={selected.has(r.id)} onChange={(e) => setSelected((s) => { const n = new Set(s); if (e.target.checked) n.add(r.id); else n.delete(r.id); return n; })} /></span>
                    <span role="gridcell" style={{ inlineSize: 60 }} className={styles.muted}><button type="button" className={styles.linkBtn} aria-label={`Open ${r.display_name}`} title="Open this record" data-testid={`rec-open-${r.id}`} onClick={(e) => morphInPlace((e.currentTarget as HTMLElement).closest('[role="row"]'), () => { pushRecent(connectionId, { model, id: r.id, name: r.display_name }); flushSync(() => setSheetId(r.id)); }, ".rec-sheet")}>{r.id}</button></span>
                    {cols.map((c) => {
                      const f = fmap.get(c);
                      const st = staged.get(`${r.id}:${c}`);
                      const isEdit = editing?.id === r.id && editing.field === c;
                      return (
                        <span role="gridcell" key={c} style={{ flex: 1, minInlineSize: 120, overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis" }}
                          tabIndex={editable(f) ? 0 : -1} aria-readonly={!editable(f)} title={editable(f) ? "Double-click or press Enter to edit" : f?.why_not ?? undefined}
                          onDoubleClick={() => editable(f) && setEditing({ id: r.id, field: c, value: "" })}
                          onKeyDown={(e) => { if (e.key === "Enter" && editable(f) && !isEdit) setEditing({ id: r.id, field: c, value: "" }); }} data-testid={`cell-${r.id}-${c}`}>
                          {isEdit && f ? (
                            <ValueInput f={f} label={`New ${f.label}`} value={editing.value} autoFocus onChange={(v) => setEditing({ ...editing, value: v })}
                              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); commitCell(); } if (e.key === "Escape") setEditing(null); }} />
                          ) : st ? <span><span aria-label="Changed, not saved yet">• </span>{showValue(st.value && typeof st.value === "object" ? (st.value as { ref?: string }).ref : st.value, f)}</span> : showValue(r[c], f)}
                        </span>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>
          )}
          <div className={styles.row}>
            <Button size="sm" variant="secondary" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button>
            <span>Page {page + 1} of {pages}</span>
            <Button size="sm" variant="secondary" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>Next</Button>
            <label className={styles.row}>Per page <select value={limit} onChange={(e) => { setLimit(Number(e.target.value)); setPage(0); }}>{[80, 200, 500].map((n) => <option key={n} value={n}>{n}</option>)}</select></label>
          </div>
          {sheetId !== null && rows.find((x) => x.id === sheetId) ? (() => {
            const r = rows.find((x) => x.id === sheetId)!;
            return (
              <aside className="rec-sheet" role="dialog" aria-label={r.display_name} data-testid="rec-sheet" onKeyDown={(e) => { if (e.key === "Escape") setSheetId(null); }}>
                <header className="rec-sheet-head"><h2>{r.display_name}</h2><Button size="sm" variant="ghost" onClick={() => setSheetId(null)} autoFocus>Close</Button></header>
                <dl>{cols.map((c) => <div key={c}><dt>{fmap.get(c)?.label ?? c}</dt><dd>{showValue(r[c], fmap.get(c))}</dd></div>)}</dl>
              </aside>
            );
          })() : null}
          {!meta.view_only ? (
            <div className={styles.grid2}>
              <section className={styles.card} aria-labelledby="bulk-h">
                <h2 id="bulk-h">Set a field on the {selected.size} selected</h2>
                <div className={styles.row}>
                  <select aria-label="Field to set" value={bulk.field} onChange={(e) => setBulk({ field: e.target.value, value: "" })} data-testid="rec-bulk-field"><option value="">Choose a field</option>{editFields.map((f) => <option key={f.name} value={f.name}>{f.label}</option>)}</select>
                  {bulk.field ? <ValueInput f={fmap.get(bulk.field)!} label="Value to set" value={bulk.value} onChange={(v) => setBulk({ ...bulk, value: v })} /> : null}
                  <Button size="sm" variant="secondary" disabled={!bulk.field || !selected.size} onClick={() => { const f = fmap.get(bulk.field)!; stage([...selected].map((id) => ({ id, field: f.name, value: toValue(f, bulk.value) }))); }} data-testid="rec-bulk-apply">Hold {selected.size} edits</Button>
                </div>
              </section>
              <section className={styles.card} aria-labelledby="fr-h">
                <h2 id="fr-h">Find and replace</h2>
                <div className={styles.row}>
                  <select aria-label="Text field" value={fr.field} onChange={(e) => setFr({ ...fr, field: e.target.value })}><option value="">Choose a text field</option>{textFields.map((f) => <option key={f.name} value={f.name}>{f.label}</option>)}</select>
                  <input aria-label="Find" value={fr.find} onChange={(e) => setFr({ ...fr, find: e.target.value })} placeholder="Find" />
                  <input aria-label="Replace with" value={fr.replace} onChange={(e) => setFr({ ...fr, replace: e.target.value })} placeholder="Replace with" />
                  <Button size="sm" variant="secondary" disabled={!fr.field || !fr.find} loading={busy === "fr"} onClick={() => act("fr", async () => {
                    const out = await recordsApi.replacePreview(connectionId, model, { field: fr.field, find: fr.find, replace: fr.replace, ids: selected.size ? [...selected] : undefined, filters, search });
                    setStaged((m) => { const n = new Map(m); out.edits.forEach((e) => n.set(`${e.id}:${e.field}`, { id: e.id, field: e.field, value: e.value, old: e.old })); return n; });
                    setNotes([`Find and replace held ${out.count} edits${selected.size ? " on the selected records" : " on every matching record"}.`]);
                  })} data-testid="rec-fr">Find</Button>
                </div>
              </section>
              <section className={styles.card} aria-labelledby="paste-h">
                <h2 id="paste-h">Paste rows from a spreadsheet</h2>
                <textarea aria-label="Pasted rows" rows={3} value={paste} onChange={(e) => setPaste(e.target.value)} placeholder={"id\tEmail\n12\tada@example.com"} style={{ inlineSize: "100%" }} data-testid="rec-paste" />
                <Button size="sm" variant="secondary" disabled={!paste.trim()} onClick={() => { const out = parsePaste(paste, meta.fields); setNotes(out.problems); if (out.edits.length) stage(out.edits); }} data-testid="rec-paste-apply">Hold these edits</Button>
              </section>
            </div>
          ) : null}
          {notes.length ? <ul className={styles.list}>{notes.map((n, i) => <li key={i}><Status tone="info">{n}</Status></li>)}</ul> : null}
          {staged.size ? (
            <section className={styles.section} aria-labelledby="held-h" data-testid="rec-held">
              <h2 id="held-h">{staged.size} edits held, nothing written yet</h2>
              <ul className={styles.list}>{[...staged.values()].slice(0, 15).map((e) => <li key={`${e.id}:${e.field}`}>#{e.id} {fmap.get(e.field)?.label ?? e.field}: {showValue(e.old, fmap.get(e.field))} → {showValue(e.value && typeof e.value === "object" ? (e.value as { ref?: string }).ref : e.value, fmap.get(e.field))}</li>)}</ul>
              <div className={styles.row}>
                <Button variant="secondary" onClick={() => setStaged(new Map())}>Clear</Button>
                <Button variant="primary" loading={busy === "plan"} onClick={() => void makePlan()} data-testid="rec-make-plan">Make the plan and check it</Button>
              </div>
            </section>
          ) : null}
        </>
      )}
    </>
  );
}
