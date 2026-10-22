"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import {
  changeApi, type Batch, type BatchCheck, type ChangeRun, type ChangeTool as Tool, type DuplicateGroup, type EditableField,
} from "@/lib/api/suite";
import { errText, useSuite } from "./SuiteContext";
import { PageHead, SafetyLevel, Status, fmtWhen, type Level } from "./parts";
import styles from "./Suite.module.css";
import { Term } from "@/components/ui/Term";

/** Change records (spec 8): Pick, Choose, Check, Run, Review. Same flow for every tool. */
export const TOOLS: Record<Tool, { title: string; purpose: string; level: Level; models: string[] }> = {
  transitions: { title: "Move forward", purpose: "Press one of Odoo's own buttons on many records, checked first.", level: "hard", models: [] },
  edit: { title: "Edit a field", purpose: "Set one field on many records, checked first, with undo.", level: "undo", models: ["sale.order", "purchase.order", "crm.lead", "res.partner", "product.template", "project.task"] },
  duplicates: { title: "Merge duplicates", purpose: "Find records that are the same thing and merge them. The others are archived, not deleted.", level: "undo", models: ["res.partner", "crm.lead", "product.template"] },
  activities: { title: "Activities", purpose: "Share out to-dos over many records and people.", level: "undo", models: ["crm.lead", "sale.order", "res.partner", "purchase.order", "project.task"] },
  portal: { title: "Portal access", purpose: "Give or remove portal access for many contacts, at a steady pace.", level: "undo", models: ["res.partner"] },
  security: { title: "Security groups", purpose: "Add or remove groups for many users at once. Accounting rights stay in Odoo.", level: "undo", models: ["res.users"] },
  message: { title: "Send a message", purpose: "Post a note or a message to followers on many records.", level: "hard", models: ["res.partner", "crm.lead", "sale.order", "purchase.order", "project.task", "product.template"] },
  recompute: { title: "Refresh computed values", purpose: "Ask Odoo to recompute a stored computed field on many records.", level: "hard", models: ["sale.order", "purchase.order", "crm.lead", "res.partner", "product.template", "project.task"] },
};
const MODEL_WORD: Record<string, string> = {
  "sale.order": "Sales orders", "purchase.order": "Purchase orders", "crm.lead": "Leads", "res.partner": "Contacts", "product.template": "Products", "project.task": "Tasks", "res.users": "Users",
};
const STEPS = ["Pick", "Choose", "Check", "Run", "Review"] as const;
const VERDICT: Record<string, string> = { ready: "Ready", no_change: "Nothing to change", blocked: "Blocked", over_cap: "Over the limit" };
const RSTATE: Record<string, string> = { waiting: "Waiting", done: "Done", no_change: "Nothing to change", skipped: "Skipped", failed: "Failed" };

function Tabs({ active }: { active: Tool }) {
  const { connectionId } = useSuite();
  return (
    <nav aria-label="Tools" className={styles.row}>
      {(Object.keys(TOOLS) as Tool[]).map((k) => <Link key={k} href={`/connections/${connectionId}/suite/change/${k}`} aria-current={k === active ? "page" : undefined}>{TOOLS[k].title}</Link>)}
      <Link href={`/connections/${connectionId}/suite/change/records`}>Record editor</Link>
    </nav>
  );
}

function Stepper({ at }: { at: number }) {
  return (
    <ol className={styles.row} aria-label="Steps" data-testid="change-stepper">
      {STEPS.map((s, i) => <li key={s} aria-current={i === at ? "step" : undefined} className={i === at ? undefined : styles.muted}>{i + 1}. {s}</li>)}
    </ol>
  );
}

export function parseIds(text: string): number[] {
  return [...new Set(text.split(/[\s,;]+/).map((x) => parseInt(x.replace(/^#/, ""), 10)).filter((n) => Number.isFinite(n) && n > 0))];
}

export function ChangeRecords({ tool }: { tool: string }) {
  const t = (tool in TOOLS ? tool : "edit") as Tool;
  const { connectionId } = useSuite();
  const router = useRouter();
  const path = usePathname() ?? "";
  const params = useSearchParams();
  const batchParam = params?.get("batch") ?? null;
  const [step, setStep] = useState(0);
  const [model, setModel] = useState<string>(TOOLS[t].models[0] ?? "sale.order");
  const [scope, setScope] = useState<"all" | "ids" | "name">("ids");
  const [idsText, setIdsText] = useState("");
  const [nameText, setNameText] = useState("");
  const [change, setChange] = useState<Record<string, unknown>>({});
  const [batch, setBatch] = useState<Batch | null>(null);
  const [check, setCheck] = useState<BatchCheck | null>(null);
  const [run, setRun] = useState<ChangeRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!batchParam) return;
    changeApi.get(connectionId, batchParam).then((b) => {
      setBatch(b); setModel(b.payload.model); setChange(b.payload.change);
      if (b.payload.ids.length) { setScope("ids"); setIdsText(b.payload.ids.join(", ")); } else setScope("all");
      setStep(1);
    }, (e: unknown) => setError(errText(e)));
  }, [batchParam, connectionId]);

  const domain = useCallback((): unknown[] => {
    const base = batch && batch.payload.domain.length && scope === "all" ? batch.payload.domain : [];
    if (scope === "name" && nameText.trim()) return [["display_name", "ilike", nameText.trim()]];
    return base;
  }, [batch, scope, nameText]);

  async function act(name: string, fn: () => Promise<unknown>) {
    setBusy(name); setError(null);
    try { await fn(); } catch (e) { setError(errText(e)); } finally { setBusy(null); }
  }
  async function save(): Promise<Batch> {
    const body = { tool: t, model, domain: domain(), ids: scope === "ids" ? parseIds(idsText) : [], change, name: `${TOOLS[t].title} on ${MODEL_WORD[model] ?? model}` };
    const b = batch ? await changeApi.update(connectionId, batch.id, body) : await changeApi.create(connectionId, body);
    setBatch(b);
    return b;
  }
  async function doCheck() {
    await act("check", async () => { const b = await save(); setCheck(await changeApi.check(connectionId, b.id)); setStep(2); const fresh = await changeApi.get(connectionId, b.id); setBatch(fresh); });
  }
  async function doRun() {
    await act("run", async () => {
      const r = await changeApi.run(connectionId, batch!.id);
      setRun(r); setStep(3);
    });
  }
  useEffect(() => {
    if (!run || !["queued", "running"].includes(run.payload.state)) { if (run && step === 3) setStep(4); return; }
    const h = setTimeout(() => { changeApi.getRun(connectionId, run.id).then(setRun, (e: unknown) => setError(errText(e))); }, 1500);
    return () => clearTimeout(h);
  }, [run, connectionId, step]);

  const approval = batch?.payload.approval ?? null;
  const approved = approval?.status === "approved";
  const canRun = !!check?.receipt && (!check.needs_approval || approved);
  const reset = () => { setStep(0); setCheck(null); setRun(null); setBatch(null); router.push(path); };

  return (
    <>
      <PageHead title={TOOLS[t].title} purpose={TOOLS[t].purpose} actions={<SafetyLevel level={TOOLS[t].level} />} />
      <Tabs active={t} />
      <Stepper at={step} />
      {error ? <Status tone="danger">{error}</Status> : null}
      {step <= 1 ? (
        <section className={styles.section} aria-labelledby="pick-h">
          <h2 id="pick-h">1. Pick the records</h2>
          {t === "transitions" ? <TransitionModel model={model} setModel={(m) => { setModel(m); setChange({}); }} /> : (
            <label className={styles.row}><Term tech="ir.model">Record type</Term>
              <select value={model} onChange={(e) => { setModel(e.target.value); setChange({}); }} data-testid="change-model">
                {TOOLS[t].models.map((m) => <option key={m} value={m}>{MODEL_WORD[m] ?? m}</option>)}
              </select>
            </label>
          )}
          {t !== "duplicates" ? (
            <fieldset className={styles.row}>
              <legend className={styles.muted}>Which records</legend>
              <label className={styles.row}><input type="radio" name="scope" checked={scope === "ids"} onChange={() => setScope("ids")} /> These record numbers</label>
              <label className={styles.row}><input type="radio" name="scope" checked={scope === "name"} onChange={() => setScope("name")} /> Name contains</label>
              <label className={styles.row}><input type="radio" name="scope" checked={scope === "all"} onChange={() => setScope("all")} /> All{batch?.payload.domain.length ? " that match the plan from Ask" : ""}</label>
              {scope === "ids" ? <input aria-label="Record numbers" value={idsText} onChange={(e) => setIdsText(e.target.value)} placeholder="12, 15, 18" data-testid="change-ids" /> : null}
              {scope === "name" ? <input aria-label="Name contains" value={nameText} onChange={(e) => setNameText(e.target.value)} /> : null}
            </fieldset>
          ) : null}
          <h2>2. Choose the change</h2>
          <Choose tool={t} model={model} change={change} setChange={setChange} />
          <div className={styles.row}><Button variant="primary" loading={busy === "check"} onClick={doCheck} data-testid="change-check">Check</Button></div>
        </section>
      ) : null}
      {step === 2 && check ? (
        <section className={styles.section} aria-labelledby="check-h" data-testid="change-check-report">
          <h2 id="check-h">3. Check</h2>
          {check.refused ? <Status tone="danger">{check.refused}</Status> : (
            <>
              <Status tone={check.counts.ready ? "success" : "warning"}>
                {check.counts.ready} ready · {check.counts.no_change ?? 0} nothing to change · {check.counts.blocked ?? 0} blocked{check.over_cap ? ` · ${check.over_cap} over this run's limit of ${check.limits.cap}` : ""}.
                {check.receipt ? " Nothing was written. This check is good for one hour for exactly these records." : ""}
              </Status>
              {check.also?.length ? <><h3>What Odoo will also do</h3><ul className={styles.list}>{check.also.map((a) => <li key={a}>{a}</li>)}</ul></> : null}
              {check.needs_approval ? (
                <Status tone={approved ? "success" : "warning"}>
                  {approved ? `Approved by ${approval?.decided_by ?? "a manager"}.` : approval?.status === "pending" ? `Waiting for approval, asked by ${approval.requested_by ?? "you"}. Someone else approves it in Safety > Approvals.`
                    : `This needs a manager's approval (an accounting button, or more than ${check.threshold} records that are hard to undo).`}
                </Status>
              ) : null}
              <RecordTable check={check} />
            </>
          )}
          <div className={styles.row}>
            <Button variant="secondary" onClick={() => setStep(1)}>Back</Button>
            {check.needs_approval && !approved && approval?.status !== "pending" ? <Button loading={busy === "ask"} onClick={() => act("ask", async () => { await changeApi.requestApproval(connectionId, batch!.id); setBatch(await changeApi.get(connectionId, batch!.id)); })} data-testid="change-ask-approval">Ask for approval</Button> : null}
            <Button variant="primary" disabled={!canRun} loading={busy === "run"} onClick={doRun} data-testid="change-run">Run on {check.counts.ready} records</Button>
          </div>
        </section>
      ) : null}
      {step >= 3 && run ? <RunPanel run={run} setRun={setRun} reset={reset} /> : null}
    </>
  );
}

function TransitionModel({ model, setModel }: { model: string; setModel: (m: string) => void }) {
  const { connectionId } = useSuite();
  const [types, setTypes] = useState<{ model: string; label: string }[]>([]);
  useEffect(() => { changeApi.buttons(connectionId).then((r) => { setTypes(r.record_types); if (r.record_types.length && !r.record_types.some((x) => x.model === model)) setModel(r.record_types[0].model); }, () => undefined); }, [connectionId]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <label className={styles.row}><Term tech="ir.model">Record type</Term>
      <select value={model} onChange={(e) => setModel(e.target.value)} data-testid="change-model">{types.map((x) => <option key={x.model} value={x.model}>{x.label}</option>)}</select>
    </label>
  );
}

function Choose({ tool, model, change, setChange }: { tool: Tool; model: string; change: Record<string, unknown>; setChange: (c: Record<string, unknown>) => void }) {
  const { connectionId } = useSuite();
  const [buttons, setButtons] = useState<{ key: string; label: string; money: boolean; effects: string[] }[]>([]);
  const [fields, setFields] = useState<EditableField[]>([]);
  const [users, setUsers] = useState<{ id: number; name: string }[]>([]);
  const [groups, setGroups] = useState<DuplicateGroup[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [secGroups, setSecGroups] = useState<{ id: number; name: string; locked: boolean }[]>([]);
  const [computed, setComputed] = useState<{ name: string; label: string }[]>([]);
  useEffect(() => {
    if (tool === "security") changeApi.groups(connectionId).then((r) => setSecGroups(r.groups), (e: unknown) => setError(errText(e)));
    if (tool === "recompute") changeApi.computed(connectionId, model).then((r) => setComputed(r.fields), (e: unknown) => setError(errText(e)));
    if (tool === "transitions") changeApi.buttons(connectionId).then((r) => setButtons(r.record_types.find((x) => x.model === model)?.buttons ?? []), () => undefined);
    if (tool === "edit") changeApi.fields(connectionId, model).then((r) => setFields(r.fields), (e: unknown) => setError(errText(e)));
    if (tool === "activities") changeApi.users(connectionId).then((r) => setUsers(r.users), () => undefined);
  }, [tool, model, connectionId]);
  const set = (k: string, v: unknown) => setChange({ ...change, [k]: v });
  if (tool === "transitions") {
    const b = buttons.find((x) => x.key === change.button);
    return (
      <div className={styles.row}>
        <label className={styles.row}>Button
          <select value={String(change.button ?? "")} onChange={(e) => set("button", e.target.value)} data-testid="change-button">
            <option value="">Choose</option>{buttons.map((x) => <option key={x.key} value={x.key}>{x.label}</option>)}
          </select>
        </label>
        {b?.money ? <label className={styles.row}>Reason (needed for accounting) <input value={String(change.reason ?? "")} onChange={(e) => set("reason", e.target.value)} /></label> : null}
      </div>
    );
  }
  if (tool === "edit") {
    const f = fields.find((x) => x.name === change.field);
    const v = change.value;
    return (
      <div className={styles.row}>
        {error ? <Status tone="danger">{error}</Status> : null}
        <label className={styles.row}>Field
          <select value={String(change.field ?? "")} onChange={(e) => setChange({ field: e.target.value })} data-testid="change-field">
            <option value="">Choose</option>{fields.map((x) => <option key={x.name} value={x.name}>{x.label}</option>)}
          </select>
        </label>
        {f ? (
          <label className={styles.row}>New value
            {f.choices.length ? (
              <select value={String(v ?? "")} onChange={(e) => set("value", e.target.value)}><option value="">Choose</option>{f.choices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}</select>
            ) : f.type === "boolean" ? (
              <select value={v === true ? "yes" : v === false ? "no" : ""} onChange={(e) => set("value", e.target.value === "yes")}><option value="">Choose</option><option value="yes">Yes</option><option value="no">No</option></select>
            ) : f.type === "many2one" ? (
              <input value={typeof v === "object" && v ? String((v as { ref?: string }).ref ?? "") : ""} onChange={(e) => set("value", { ref: e.target.value })} placeholder="Exact name" data-testid="change-value" />
            ) : (
              <input value={v === undefined ? "" : String(v)} onChange={(e) => set("value", ["integer", "float", "monetary"].includes(f.type) ? Number(e.target.value) : e.target.value)} data-testid="change-value" />
            )}
          </label>
        ) : null}
      </div>
    );
  }
  if (tool === "activities") {
    const chosen = (change.user_ids as number[] | undefined) ?? [];
    const due = (change.due as { mode?: string; days?: number } | undefined) ?? { mode: "in_days", days: 3 };
    return (
      <div className={styles.row}>
        <fieldset className={styles.row}><legend className={styles.muted}>Share out to</legend>
          {users.map((u) => <label key={u.id} className={styles.row}><input type="checkbox" checked={chosen.includes(u.id)} onChange={(e) => set("user_ids", e.target.checked ? [...chosen, u.id] : chosen.filter((x) => x !== u.id))} /> {u.name}</label>)}
        </fieldset>
        <label className={styles.row}>What to do <input value={String(change.summary ?? "")} onChange={(e) => set("summary", e.target.value)} /></label>
        <label className={styles.row}>Due
          <select value={due.mode} onChange={(e) => set("due", { ...due, mode: e.target.value })}><option value="in_days">in</option><option value="spread">spread over the next</option></select>
          <input inputMode="numeric" size={3} value={String(due.days ?? 0)} onChange={(e) => set("due", { ...due, days: parseInt(e.target.value, 10) || 0 })} /> {due.mode === "spread" ? "working days" : "days"}
        </label>
      </div>
    );
  }
  if (tool === "security") {
    const pick = (k: "add" | "remove", label: string) => (
      <label className={styles.row}>{label}
        <select multiple value={((change[k] as number[] | undefined) ?? []).map(String)} onChange={(e) => set(k, Array.from(e.target.selectedOptions).map((o) => Number(o.value)))} data-testid={`change-sec-${k}`}>
          {secGroups.map((g) => <option key={g.id} value={g.id} disabled={g.locked} title={g.locked ? "Accounting rights are given in Odoo (money guard)" : undefined}>{g.name}{g.locked ? " (in Odoo only)" : ""}</option>)}
        </select>
      </label>
    );
    return <div className={styles.row}>{error ? <Status tone="danger">{error}</Status> : null}{pick("add", "Add groups")}{pick("remove", "Remove groups")}</div>;
  }
  if (tool === "message") {
    const kind = (change.kind as string | undefined) ?? "note";
    return (
      <div>
        <div className={styles.row} role="radiogroup" aria-label="Message kind">
          <label className={styles.row}><input type="radio" name="kind" checked={kind === "note"} onChange={() => set("kind", "note")} /> Internal note (nobody emailed)</label>
          <label className={styles.row}><input type="radio" name="kind" checked={kind === "comment"} onChange={() => set("kind", "comment")} /> Message to followers (emails them)</label>
        </div>
        <label className={styles.row}>Message
          <textarea value={String(change.body ?? "")} onChange={(e) => setChange({ kind, ...change, body: e.target.value })} placeholder="Use {name} for each record's name" rows={4} data-testid="change-body" />
        </label>
        <SendLater value={(change.send_at as string | undefined) ?? ""} onChange={(v) => setChange({ kind, ...change, send_at: v || undefined, repeat: v ? change.repeat : undefined })} />
        {change.send_at ? <RepeatPick value={change.repeat as Repeat | undefined} onChange={(r) => setChange({ kind, ...change, repeat: r })} /> : null}
      </div>
    );
  }
  if (tool === "recompute") {
    return (
      <div className={styles.row}>
        {error ? <Status tone="danger">{error}</Status> : null}
        <label className={styles.row}>Computed field
          <select value={String(change.field ?? "")} onChange={(e) => setChange({ field: e.target.value })} data-testid="change-computed">
            <option value="">Choose</option>{computed.map((x) => <option key={x.name} value={x.name}>{x.label}</option>)}
          </select>
        </label>
      </div>
    );
  }
  if (tool === "portal") {
    return (
      <div className={styles.row} role="radiogroup" aria-label="Portal">
        <label className={styles.row}><input type="radio" name="portal" checked={change.action === "grant"} onChange={() => set("action", "grant")} /> Give portal access</label>
        <label className={styles.row}><input type="radio" name="portal" checked={change.action === "revoke"} onChange={() => set("action", "revoke")} /> Remove portal access</label>
      </div>
    );
  }
  const chosen = (change.groups as { keep: number; merge: number[] }[] | undefined) ?? [];
  return (
    <div>
      <Button size="sm" variant="secondary" onClick={() => changeApi.scan(connectionId, model, [], ["email", "phone", "name"]).then((r) => setGroups(r.groups), (e: unknown) => setError(errText(e)))} data-testid="change-scan">Find duplicates</Button>
      {error ? <Status tone="danger">{error}</Status> : null}
      {groups ? (groups.length ? (
        <ul className={styles.list} data-testid="change-groups">
          {groups.map((g) => {
            const on = chosen.find((c) => c.merge.length && g.ids.includes(c.keep));
            const keep = on?.keep ?? g.keep;
            const toggle = (k: number, checked: boolean) => set("groups", checked ? [...chosen.filter((c) => !g.ids.includes(c.keep)), { keep: k, merge: g.ids.filter((i) => i !== k) }] : chosen.filter((c) => !g.ids.includes(c.keep)));
            return (
              <li key={g.ids.join("-")} className={styles.card}>
                <label className={styles.row}><input type="checkbox" checked={!!on} onChange={(e) => toggle(keep, e.target.checked)} /> <strong>{g.strength} match</strong> <span className={styles.muted}>{g.reasons.join(", ")}</span></label>
                {g.records.map((r) => (
                  <label key={String(r.id)} className={styles.row}><input type="radio" name={`keep-${g.ids[0]}`} checked={keep === r.id} onChange={() => toggle(Number(r.id), true)} /> Keep #{String(r.id)} {String(r.name ?? "")} <span className={styles.muted}>{String(r.email || "")}</span></label>
                ))}
              </li>
            );
          })}
        </ul>
      ) : <p className={styles.muted}>No duplicates found.</p>) : null}
    </div>
  );
}

function RecordTable({ check }: { check: BatchCheck }) {
  const rows = check.records.slice(0, 200);
  return (
    <table className={styles.table} data-testid="change-records">
      <thead><tr><th scope="col">Record</th><th scope="col">Verdict</th><th scope="col">Now</th><th scope="col">After</th></tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={`${r.group ?? ""}${r.id}`} data-verdict={r.verdict}>
            <td>{r.name}</td>
            <td>{VERDICT[r.verdict] ?? r.verdict}{r.reason ? `: ${r.reason}` : ""}{r.fix ? <div className={styles.muted}>{r.fix}</div> : null}</td>
            <td className={styles.muted}>{r.now === undefined || r.now === false ? "" : String(r.now)}</td>
            <td>{r.after === undefined ? (r.due ? `Due ${r.due}` : "") : String(r.after)}</td>
          </tr>
        ))}
      </tbody>
      {check.records.length > rows.length ? <caption className={styles.muted}>First {rows.length} of {check.records.length} shown.</caption> : null}
    </table>
  );
}

function RunPanel({ run, setRun, reset }: { run: ChangeRun; setRun: (r: ChangeRun) => void; reset: () => void }) {
  const { connectionId } = useSuite();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const p = run.payload;
  const counts = p.records.reduce<Record<string, number>>((a, r) => ({ ...a, [r.state]: (a[r.state] ?? 0) + 1 }), {});
  const live = ["queued", "running"].includes(p.state);
  if (p.state === "scheduled" || p.state === "cancelled") {
    return (
      <section className={styles.section} aria-labelledby="run-h" data-testid="change-run-panel">
        <h2 id="run-h">4. Send later</h2>
        <Status tone={p.state === "scheduled" ? "info" : "warning"} aria-live="polite">
          {p.state === "scheduled" ? `Scheduled: ${p.records.length} messages go out ${fmtWhen(p.fire_at)}${p.repeat ? `, then ${p.repeat.every} until ${fmtWhen(p.repeat.until)} (send ${p.occurrence ?? 1})` : ""}. Each record is checked again just before.` : "Cancelled before it was sent. Nothing went out."}
        </Status>
        {error ? <Status tone="danger">{error}</Status> : null}
        <div className={styles.row}>
          {p.state === "scheduled" ? <Reschedule repeating={Boolean(p.repeat)} onMove={(iso, move) => act("move", async () => { await changeApi.reschedule(connectionId, run.id, iso, move); setRun(await changeApi.getRun(connectionId, run.id)); })} busy={busy === "move"} /> : null}
          {p.state === "scheduled" ? <Button variant="danger" loading={busy === "cancel"} onClick={() => act("cancel", async () => { await changeApi.cancel(connectionId, run.id); setRun(await changeApi.getRun(connectionId, run.id)); })} data-testid="change-cancel">{p.repeat ? "Cancel this and later sends" : "Cancel the send"}</Button> : null}
          <Button variant="secondary" onClick={reset}>Start another</Button>
        </div>
      </section>
    );
  }
  async function act(name: string, fn: () => Promise<unknown>) {
    setBusy(name); setError(null);
    try { await fn(); } catch (e) { setError(errText(e)); } finally { setBusy(null); }
  }
  async function exportCsv() {
    const blob = await changeApi.exportCsv(connectionId, run.id);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `change-run-${run.id}.csv`; a.click(); URL.revokeObjectURL(a.href);
  }
  return (
    <section className={styles.section} aria-labelledby="run-h" data-testid="change-run-panel">
      <h2 id="run-h">{live ? "4. Run" : "5. Review"}{p.kind === "undo" ? " (undo)" : ""}</h2>
      <Status tone={live ? "busy" : p.state === "done" ? "success" : "warning"} aria-live="polite">
        {live ? "Running" : p.state === "done" ? "Finished" : p.state === "stopped" ? "Stopped" : "Did not run"}{p.message ? `: ${p.message}` : ""}.
        {" "}{counts.done ?? 0} done · {counts.no_change ?? 0} nothing to change · {counts.skipped ?? 0} skipped · {counts.failed ?? 0} failed · {counts.waiting ?? 0} waiting.
      </Status>
      {error ? <Status tone="danger">{error}</Status> : null}
      <div className={styles.row}>
        {live ? <Button variant="danger" loading={busy === "stop"} onClick={() => act("stop", () => changeApi.stop(connectionId, run.id))} data-testid="change-stop">Stop after this batch</Button> : null}
        {!live && p.kind === "run" && (counts.done ?? 0) > 0 ? <Button loading={busy === "undo"} onClick={() => act("undo", async () => setRun(await changeApi.undo(connectionId, run.id)))} data-testid="change-undo">Undo this run</Button> : null}
        {!live ? <Button variant="secondary" onClick={() => void exportCsv()}>Export the results</Button> : null}
        {!live ? <Button variant="secondary" onClick={reset}>Start another</Button> : null}
      </div>
      <table className={styles.table}>
        <thead><tr><th scope="col">Record</th><th scope="col">Result</th></tr></thead>
        <tbody>{p.records.slice(0, 200).map((r) => <tr key={r.id} data-state={r.state}><td>{r.name}</td><td>{RSTATE[r.state] ?? r.state}{r.message ? `: ${r.message}` : ""}</td></tr>)}</tbody>
      </table>
    </section>
  );
}


/** Send now or at a chosen time (stored as UTC, up to 30 days ahead). */
function SendLater({ value, onChange }: { value: string; onChange: (iso: string) => void }) {
  const later = Boolean(value);
  const local = (iso: string) => { const d = new Date(iso); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };
  const min = local(new Date(Date.now() + 5 * 60000).toISOString());
  const max = local(new Date(Date.now() + 30 * 86400000).toISOString());
  return (
    <div className={styles.row} role="radiogroup" aria-label="When to send">
      <label className={styles.row}><input type="radio" name="when" checked={!later} onChange={() => onChange("")} /> Send now</label>
      <label className={styles.row}><input type="radio" name="when" checked={later} onChange={() => onChange(new Date(Date.now() + 3600000).toISOString())} /> Send later</label>
      {later ? (
        <label className={styles.row}>At
          <input type="datetime-local" value={local(value)} min={min} max={max} onChange={(e) => e.target.value && onChange(new Date(e.target.value).toISOString())} data-testid="change-send-at" />
        </label>
      ) : null}
    </div>
  );
}

type Repeat = { every: "daily" | "weekly" | "monthly"; until: string };

/** Repeat a scheduled message (daily, weekly or monthly) until an end date; each send re-checks every record. */
function RepeatPick({ value, onChange }: { value?: Repeat; onChange: (r: Repeat | undefined) => void }) {
  const until = value?.until ? new Date(value.until).toISOString().slice(0, 10) : "";
  return (
    <div className={styles.row}>
      <label className={styles.row}>Repeat
        <select value={value?.every ?? ""} onChange={(e) => onChange(e.target.value ? { every: e.target.value as Repeat["every"], until: value?.until ?? new Date(Date.now() + 30 * 86400000).toISOString() } : undefined)} data-testid="change-repeat">
          <option value="">Doesn&apos;t repeat</option>
          <option value="daily">Every day</option>
          <option value="weekly">Every week</option>
          <option value="monthly">Every month</option>
        </select>
      </label>
      {value ? (
        <label className={styles.row}>Until
          <input type="date" value={until} onChange={(e) => e.target.value && onChange({ ...value, until: new Date(`${e.target.value}T23:59:00`).toISOString() })} data-testid="change-repeat-until" />
        </label>
      ) : null}
    </div>
  );
}

/** Move a pending send to another time. Only the time changes; records are still checked when it goes out. */
function Reschedule({ onMove, busy, repeating }: { onMove: (iso: string, move: "this" | "series") => void; busy: boolean; repeating: boolean }) {
  const [v, setV] = useState("");
  const [move, setMove] = useState<"this" | "series">("this");
  return (
    <span className={styles.row}>
      <label className={styles.row}>New time <input type="datetime-local" value={v} onChange={(e) => setV(e.target.value)} data-testid="change-reschedule-at" /></label>
      {repeating ? (
        <select value={move} onChange={(e) => setMove(e.target.value as "this" | "series")} aria-label="Which sends move" data-testid="change-reschedule-scope">
          <option value="this">Only this send</option>
          <option value="series">This and later sends</option>
        </select>
      ) : null}
      <Button variant="secondary" loading={busy} disabled={!v} onClick={() => onMove(new Date(v).toISOString(), move)} data-testid="change-reschedule">Move the send</Button>
    </span>
  );
}
