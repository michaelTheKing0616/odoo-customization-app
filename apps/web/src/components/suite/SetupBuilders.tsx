"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { IconImport as Upload, X } from "@/components/ui/icons";
import { suiteApi, type BuilderOptions, type ImportPreview, type ImportTable, type PlanStep } from "@/lib/api/suite";
import { errText, useSuite } from "./SuiteContext";
import { Status } from "./parts";
import styles from "./Suite.module.css";

type Kind = "unit" | "category" | "product" | "setting";
const KIND_WORD: Record<Kind, string> = { unit: "Unit", category: "Product category", product: "Product", setting: "Setting" };

export function readFileB64(file: File): Promise<string> {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result).split(",")[1] ?? "");
    r.onerror = () => rej(r.error);
    r.readAsDataURL(file);
  });
}

/** Build a step from plain form fields. Code still checks every step before anything runs. */
export function buildStep(kind: Kind, f: Record<string, string>): Partial<PlanStep> | string {
  const name = (f.name ?? "").trim();
  if (kind === "unit") {
    const factor = Number(f.factor);
    if (!name || !f.reference || !(factor > 0)) return "Give the unit a name, the unit it is measured against, and a number above zero.";
    return { type: "units", inputs: { name, reference: f.reference, factor } };
  }
  if (kind === "category") {
    if (!name) return "Give the category a name.";
    return { type: "create", inputs: { model: "product.category", values: { name, ...(f.parent ? { parent_id: { ref: f.parent } } : {}) } } };
  }
  if (kind === "product") {
    if (!name) return "Give the product a name.";
    const price = f.price ? Number(f.price) : undefined;
    if (f.price && !(price! >= 0)) return "The price must be a number.";
    return { type: "create", inputs: { model: "product.template", values: { name, ...(price !== undefined ? { list_price: price } : {}), ...(f.category ? { categ_id: { ref: f.category.split(" / ").pop() } } : {}) } } };
  }
  if (!f.field) return "Choose a setting.";
  const v = f.value === "on" ? true : f.value === "off" ? false : f.value;
  return { type: "setting", inputs: { values: { [f.field]: v } } };
}

function describe(s: Partial<PlanStep>): string {
  const i = (s.inputs ?? {}) as Record<string, unknown>;
  if (s.type === "units") return `Unit ${i.name} = ${i.factor} x ${i.reference}`;
  if (s.type === "setting") return `Setting ${Object.entries(i.values as object).map(([k, v]) => `${k}: ${String(v)}`).join(", ")}`;
  const vals = i.values as Record<string, unknown>;
  return `${i.model === "product.category" ? "Category" : "Product"} ${String(vals.name)}`;
}

export function StepBuilder({ onPlan }: { onPlan: (planId: string) => void }) {
  const { connectionId } = useSuite();
  const [open, setOpen] = useState(false);
  const [opts, setOpts] = useState<BuilderOptions | null>(null);
  const [kind, setKind] = useState<Kind>("unit");
  const [form, setForm] = useState<Record<string, string>>({});
  const [steps, setSteps] = useState<Partial<PlanStep>[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open && !opts) suiteApi.builderOptions(connectionId).then(setOpts, (e: unknown) => setError(errText(e))); }, [open, opts, connectionId]);
  const set = (k: string) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const setting = opts?.settings.find((x) => x.field === form.field);
  function add() {
    const s = buildStep(kind, form);
    if (typeof s === "string") { setError(s); return; }
    setError(null); setSteps((x) => [...x, s]); setForm({});
  }
  async function make() {
    setBusy(true);
    try { const p = await suiteApi.createPlan(connectionId, "Built step by step", steps.map((s, i) => ({ ...s, id: `b${i + 1}`, source: { kind: "typed" } }))); onPlan(p.id); }
    catch (e) { setError(errText(e)); } finally { setBusy(false); }
  }
  return (
    <section className={styles.section} aria-labelledby="sb-h" data-testid="suite-step-builder">
      <h2 id="sb-h">Add steps one by one</h2>
      {!open ? <Button variant="secondary" onClick={() => setOpen(true)}>Start adding steps</Button> : (
        <div className={styles.card}>
          <div className={styles.row} role="radiogroup" aria-label="What to add">
            {(Object.keys(KIND_WORD) as Kind[]).map((k) => (
              <label key={k} className={styles.row}><input type="radio" name="sb-kind" checked={kind === k} onChange={() => { setKind(k); setForm({}); setError(null); }} /> {KIND_WORD[k]}</label>
            ))}
          </div>
          <form className={styles.row} onSubmit={(e) => { e.preventDefault(); add(); }}>
            {kind !== "setting" ? <label className={styles.row}>Name <input value={form.name ?? ""} onChange={set("name")} data-testid="sb-name" /></label> : null}
            {kind === "unit" ? (
              <>
                <label className={styles.row}>equals <input inputMode="decimal" size={6} value={form.factor ?? ""} onChange={set("factor")} data-testid="sb-factor" /></label>
                <label className={styles.row}>x
                  <select value={form.reference ?? ""} onChange={set("reference")} data-testid="sb-reference">
                    <option value="">Choose a unit</option>
                    {(opts?.units ?? []).map((u) => <option key={u} value={u}>{u}</option>)}
                  </select>
                </label>
              </>
            ) : null}
            {kind === "category" ? (
              <label className={styles.row}>Inside
                <select value={form.parent ?? ""} onChange={set("parent")}><option value="">Top level</option>{(opts?.categories ?? []).map((c) => <option key={c} value={c.split(" / ").pop()}>{c}</option>)}</select>
              </label>
            ) : null}
            {kind === "product" ? (
              <>
                <label className={styles.row}>Sales price <input inputMode="decimal" size={8} value={form.price ?? ""} onChange={set("price")} /></label>
                <label className={styles.row}>Category
                  <select value={form.category ?? ""} onChange={set("category")}><option value="">Default</option>{(opts?.categories ?? []).map((c) => <option key={c} value={c}>{c}</option>)}</select>
                </label>
              </>
            ) : null}
            {kind === "setting" ? (
              <>
                <label className={styles.row}>Setting
                  <select value={form.field ?? ""} onChange={set("field")} data-testid="sb-setting">
                    <option value="">Choose a setting</option>
                    {(opts?.settings ?? []).map((x) => <option key={x.field} value={x.field}>{x.label}</option>)}
                  </select>
                </label>
                {setting ? (
                  <label className={styles.row}>Set to
                    <select value={form.value ?? ""} onChange={set("value")}>
                      <option value="">Choose</option>
                      {setting.type === "boolean" ? <><option value="on">On</option><option value="off">Off</option></> : setting.selection.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </select>
                    <span className={styles.muted}>Now: {setting.type === "boolean" ? (setting.value ? "On" : "Off") : String(setting.value ?? "not set")}</span>
                  </label>
                ) : null}
              </>
            ) : null}
            <Button type="submit" size="sm" variant="secondary">Add step</Button>
          </form>
          {error ? <Status tone="warning">{error}</Status> : null}
          {steps.length ? (
            <>
              <ol className={styles.list} data-testid="sb-steps">
                {steps.map((s, i) => (
                  <li key={i} className={styles.row}>{describe(s)}
                    <button type="button" className={styles.linkBtn} aria-label={`Remove step ${i + 1}`} onClick={() => setSteps((x) => x.filter((_, j) => j !== i))}><X aria-hidden width={14} height={14} /></button>
                  </li>
                ))}
              </ol>
              <p className={styles.muted}>Code puts these in a safe order and checks each one before anything runs.</p>
              <Button variant="primary" loading={busy} onClick={make} data-testid="sb-make">Make a plan with {steps.length} {steps.length === 1 ? "step" : "steps"}</Button>
            </>
          ) : null}
        </div>
      )}
    </section>
  );
}

/** Paste or upload any document into the import targets (catalog 2.21, spec 20.13). Odoo's own import test is the Check. */
export function ImportPanel({ onPlan }: { onPlan: (planId: string) => void }) {
  const { connectionId } = useSuite();
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [tables, setTables] = useState<ImportTable[]>([]);
  const [skip, setSkip] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const lastFile = useRef<{ filename: string; content_b64: string } | null>(null);

  async function read(body: { filename?: string; content_b64?: string; text?: string; model?: string | null }) {
    setBusy(true); setError(null);
    try {
      const pv = await suiteApi.importPreview(connectionId, { ...body, job: preview?.job ?? null });
      setPreview(pv); setTables(pv.tables); setSkip({});
      if (!pv.tables.length) setError(pv.notes.join(" ") || "No table found.");
    } catch (e) { setError(errText(e)); } finally { setBusy(false); }
  }
  async function retarget(model: string) {
    const src = lastFile.current ?? { text };
    await read({ ...src, model });
  }
  function answer(ti: number, column: string, field: string) {
    setTables((ts) => ts.map((t, i) => (i === ti ? { ...t, mapping: { ...t.mapping, [column]: field || null } } : t)));
  }
  async function make() {
    const steps = tables.filter((t) => t.step && t.model).map((t, i) => ({
      id: `imp${i + 1}`, type: "import" as const, source: { kind: "typed" },
      inputs: { ...(t.step!.inputs as object), mapping: t.mapping, skip: Object.entries(skip).filter(([k, v]) => v && k.startsWith(`${t.table}:`)).map(([k]) => k.split(":").slice(1).join(":")) },
    }));
    setBusy(true);
    try { const p = await suiteApi.createPlan(connectionId, `Import ${preview?.tables[0]?.name ?? "document"}`.slice(0, 100), steps); onPlan(p.id); }
    catch (e) { setError(errText(e)); } finally { setBusy(false); }
  }
  return (
    <section className={styles.section} aria-labelledby="imp-h" data-testid="suite-import">
      <h2 id="imp-h">Bring in a document</h2>
      <p className={styles.muted}>Paste rows or upload a CSV, Excel, Word or PDF file. Code matches columns to fields and asks about the rest. Check runs Odoo&apos;s own import test without saving.</p>
      <div className={styles.row}>
        <label htmlFor="suite-imp-file" className={styles.row}><Upload aria-hidden width={16} height={16} /> Upload a document</label>
        <input id="suite-imp-file" ref={fileRef} type="file" accept=".csv,.txt,.tsv,.xlsx,.xlsm,.docx,.pdf" disabled={busy} data-testid="suite-imp-file"
          onChange={async (e) => { const f = e.target.files?.[0]; if (!f) return; const content_b64 = await readFileB64(f); lastFile.current = { filename: f.name, content_b64 }; void read(lastFile.current); }} />
      </div>
      <label htmlFor="suite-imp-text" className={styles.mutedLine}>Or paste rows (with a header line)</label>
      <textarea id="suite-imp-text" rows={4} value={text} onChange={(e) => setText(e.target.value)} style={{ inlineSize: "100%" }} data-testid="suite-imp-text" />
      <div className={styles.row}><Button size="sm" variant="secondary" disabled={!text.trim() || busy} loading={busy} onClick={() => { lastFile.current = null; void read({ text }); }} data-testid="suite-imp-read">Read the rows</Button></div>
      {error ? <Status tone="warning">{error}</Status> : null}
      {tables.map((t, ti) => (
        <div key={t.table} className={styles.card} data-testid={`suite-imp-table-${t.table}`}>
          <p className={styles.flush}><strong>{t.name}</strong> · {t.row_count} rows</p>
          <label className={styles.row}>Goes into
            <select value={t.model ?? ""} onChange={(e) => void retarget(e.target.value)} data-testid="suite-imp-target">
              {t.candidates.map((c) => <option key={c.model} value={c.model}>{c.label} ({c.mapped} columns match)</option>)}
              {(preview?.targets ?? []).filter((x) => !t.candidates.some((c) => c.model === x.model)).map((x) => <option key={x.model} value={x.model}>{x.label}</option>)}
            </select>
          </label>
          <table className={styles.table}>
            <thead><tr><th scope="col">Column</th><th scope="col">Field</th><th scope="col">First value</th></tr></thead>
            <tbody>
              {t.headers.map((h, hi) => {
                const q = t.questions.find((x) => x.column === h);
                const key = `${t.table}:${h}`;
                return (
                  <tr key={h}>
                    <td>{h}</td>
                    <td>{q && !t.mapping[h] ? (
                      <span className={styles.row}>
                        <select aria-label={q.question} value={t.mapping[h] ?? ""} onChange={(e) => answer(ti, h, e.target.value)} disabled={!!skip[key]}>
                          <option value="">{q.question}</option>{q.options.map((o) => <option key={o.field} value={o.field}>{o.label}</option>)}
                        </select>
                        <label className={styles.row}><input type="checkbox" checked={!!skip[key]} onChange={(e) => setSkip((s) => ({ ...s, [key]: e.target.checked }))} /> Skip</label>
                      </span>
                    ) : t.mapping[h]}</td>
                    <td className={styles.muted}>{t.sample[0]?.[hi] ?? ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {t.missing_required.length ? <Status tone="warning">Odoo needs a column for: {t.missing_required.join(", ")}.</Status> : null}
        </div>
      ))}
      {tables.some((t) => t.step) ? <Button variant="primary" loading={busy} onClick={make} data-testid="suite-imp-plan">Make a plan to import</Button> : null}
    </section>
  );
}
