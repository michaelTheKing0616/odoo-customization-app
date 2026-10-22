"use client";

import { useTabBusy } from "@/components/ui/craft";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { IconImport as Upload, IconReports as FileText } from "@/components/ui/icons";
import { suiteApi, type CatalogTask, type CheckReport, type Plan, type PlanStep, type Run } from "@/lib/api/suite";
import { CheckEveryVersion } from "./EveryVersion";
import { ImportPanel, StepBuilder } from "./SetupBuilders";
import { errText, useSuite } from "./SuiteContext";
import { PageHead, SafetyLevel, StateIcon, STATE_WORD, Status, VERDICT_WORD, VerdictIcon, levelOf } from "./parts";
import styles from "./Suite.module.css";

const SOURCE_WORD: Record<string, string> = { typed: "Typed here", workbook: "From the workbook", ai: "Suggested by the assistant", undo: "From a run", catalog: "From the catalog" };

function useNav() {
  const router = useRouter();
  const path = usePathname() ?? "";
  const params = useSearchParams();
  const go = useCallback((q: Record<string, string | null>) => {
    const next = new URLSearchParams(params?.toString() ?? "");
    for (const [k, v] of Object.entries(q)) { if (v === null) next.delete(k); else next.set(k, v); }
    router.push(`${path}?${next.toString()}`);
  }, [params, path, router]);
  return { params, go };
}

/** Set up workspace (spec 20): catalog, plans, board by wave, Check with receipt, Run board, Undo. */
export function SetupWorkspace() {
  const { params } = useNav();
  const planId = params?.get("plan");
  const runId = params?.get("run");
  if (runId) return <RunBoard runId={runId} />;
  if (planId) return <PlanBoard planId={planId} />;
  return <SetupStart />;
}

function SetupStart() {
  const { connectionId } = useSuite();
  const { go } = useNav();
  const [cat, setCat] = useState<{ version: string; counts: { total: number; available: number }; tasks: CatalogTask[] } | null>(null);
  const [plans, setPlans] = useState<{ id: string; name: string; kind: string; steps: number }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [onlyHere, setOnlyHere] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    suiteApi.catalog(connectionId).then(setCat, (e: unknown) => setError(errText(e)));
    suiteApi.plans(connectionId).then((r) => setPlans(r.plans), () => undefined);
  }, [connectionId]);
  const groups = useMemo(() => {
    const out = new Map<string, CatalogTask[]>();
    for (const t of cat?.tasks ?? []) {
      if (onlyHere && t.state !== "available") continue;
      const k = `${t.rank}. ${t.rank_label}`;
      out.set(k, [...(out.get(k) ?? []), t]);
    }
    return [...out.entries()].sort(([a], [b]) => parseInt(a, 10) - parseInt(b, 10));
  }, [cat, onlyHere]);

  async function download() {
    setBusy(true);
    try {
      const blob = await suiteApi.downloadWorkbook(connectionId);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "setup-workbook.xlsx";
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) { setError(errText(e)); } finally { setBusy(false); }
  }
  async function upload(file: File) {
    setBusy(true); setNotes([]);
    try {
      const b64 = await new Promise<string>((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(String(r.result).split(",")[1] ?? "");
        r.onerror = () => rej(r.error);
        r.readAsDataURL(file);
      });
      const out = await suiteApi.uploadWorkbook(connectionId, file.name.replace(/\.xlsx$/i, "").slice(0, 100) || "Workbook setup", b64);
      setNotes(out.notes.length ? out.notes : []);
      if (out.plan) go({ plan: out.plan.id, view: "board" });
      else setNotes((n) => ["Nothing changed: every row already matches this database.", ...n]);
    } catch (e) { setError(errText(e)); } finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  return (
    <>
      <PageHead title="Set up" purpose="Plan setup work, check it without writing, then run it in waves. Every run can be undone where Odoo allows."
        actions={<Button variant="primary" onClick={download} disabled={busy}><FileText aria-hidden /> Download the setup workbook</Button>} />
      {error ? <Status tone="danger">{error}</Status> : null}
      <section className={styles.section} aria-labelledby="wb-h">
        <h2 id="wb-h">Fill in a workbook</h2>
        <p className={styles.muted}>The workbook already holds what this database has. Add or change rows, then upload it. Unchanged rows do nothing.</p>
        <div className={styles.row}>
          <label htmlFor="suite-wb" className={styles.row}><Upload aria-hidden width={16} height={16} /> Upload a filled workbook</label>
          <input id="suite-wb" ref={fileRef} type="file" accept=".xlsx" disabled={busy} onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); }} data-testid="suite-wb-input" />
        </div>
        {notes.length ? <ul className={styles.list}>{notes.map((n, i) => <li key={i}><Status tone="info">{n}</Status></li>)}</ul> : null}
      </section>
      <StepBuilder onPlan={(pid) => go({ plan: pid, view: "board" })} />
      <ImportPanel onPlan={(pid) => go({ plan: pid, view: "board" })} />
      <section className={styles.section} aria-labelledby="plans-h">
        <h2 id="plans-h">Plans</h2>
        {plans.length ? (
          <ul className={styles.list}>{plans.map((p) => <li key={p.id}><Link href={`?plan=${p.id}&view=board`}>{p.name}</Link> <span className={styles.muted}>{p.steps} steps{p.kind === "undo" ? " · undo plan" : ""}</span></li>)}</ul>
        ) : <p className={styles.muted}>No plans yet.</p>}
      </section>
      <section className={styles.section} aria-labelledby="cat-h" data-testid="suite-catalog">
        <div className={styles.row}>
          <h2 id="cat-h" className={styles.grow}>What can be set up {cat ? <span className={styles.muted}>({cat.counts.available} of {cat.counts.total} on Odoo {cat.version})</span> : null}</h2>
          <label className={styles.row}><input type="checkbox" checked={onlyHere} onChange={(e) => setOnlyHere(e.target.checked)} /> Only what this database has</label>
        </div>
        {!cat && !error ? <Status tone="busy">Reading the catalog…</Status> : null}
        {groups.map(([label, tasks]) => (
          <details key={label} className={styles.wave}>
            <summary><strong>{label}</strong> <span className={styles.muted}>{tasks.length}</span></summary>
            <table className={styles.table}>
              <thead><tr><th scope="col">Task</th><th scope="col">How Odoo does it here</th><th scope="col">Risk</th><th scope="col">Here</th></tr></thead>
              <tbody>
                {tasks.map((t) => (
                  <tr key={t.id} data-task={t.id}>
                    <td>{t.title} <span className={styles.muted}>{t.id}</span></td>
                    <td>{t.mechanism.kind}{t.mechanism.models?.length ? `: ${t.mechanism.models.join(", ")}` : ""}{t.mechanism.note ? <div className={styles.muted}>{t.mechanism.note}</div> : null}</td>
                    <td>{t.risk}</td>
                    <td>{t.state === "available" ? "Yes" : <span className={styles.muted}>{t.reason}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        ))}
      </section>
    </>
  );
}

function StepRow({ s, report }: { s: PlanStep; report?: CheckReport | null }) {
  const r = report?.steps[s.id];
  return (
    <li className={styles.step} data-verdict={r?.verdict} data-testid={`suite-step-${s.id}`}>
      {r ? <VerdictIcon verdict={r.verdict} /> : <span aria-hidden />}
      <div>
        <div>{s.label}</div>
        <div className={styles.muted}>
          {s.task ? `${s.task} · ` : ""}{SOURCE_WORD[s.source.kind] ?? s.source.kind}{s.source.ref ? ` (${s.source.ref})` : ""}{s.depends_on.length ? ` · waits for ${s.depends_on.join(", ")}` : ""}
        </div>
        {r ? <div>{VERDICT_WORD[r.verdict]}{r.message ? `: ${r.message}` : ""}</div> : null}
      </div>
      <SafetyLevel level={levelOf(s.reversibility, s.risk)} />
    </li>
  );
}

function PlanBoard({ planId }: { planId: string }) {
  const { connectionId } = useSuite();
  const { go } = useNav();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  useTabBusy(busy !== null);
  const load = useCallback(() => { suiteApi.plan(connectionId, planId).then(setPlan, (e: unknown) => setError(errText(e))); }, [connectionId, planId]);
  useEffect(() => { load(); }, [load]);
  if (error && !plan) return <Status tone="danger">{error}</Status>;
  if (!plan) return <Status tone="busy">Reading the plan…</Status>;
  const p = plan.payload;
  const report = p.check && p.check.plan_hash === p.hash ? p.check : null;
  const byId = new Map(p.steps.map((s) => [s.id, s]));
  const ready = report?.counts.ready ?? 0;
  const approved = p.approval?.status === "approved";
  const pending = p.approval?.status === "pending";
  const canRun = !!report?.receipt && report.can_apply && (!report.needs_approval || approved);

  async function act(name: string, fn: () => Promise<unknown>) {
    setBusy(name); setError(null);
    try { await fn(); } catch (e) { setError(errText(e)); } finally { setBusy(null); }
  }
  return (
    <>
      <PageHead title={plan.name} purpose={p.kind === "undo" ? "Undo plan: what the run changed, in reverse order. It is checked and run like any plan." : "Steps in the order code will run them. Installs go first, on their own."}
        actions={
          <div className={styles.row}>
            <Button variant={report ? "secondary" : "primary"} loading={busy === "check"} onClick={() => act("check", async () => { await suiteApi.check(connectionId, planId); load(); })} data-testid="suite-check">Check {p.steps.length} steps</Button>
            {report?.needs_approval && !approved && !pending ? <Button loading={busy === "approve"} onClick={() => act("approve", async () => { await suiteApi.requestApproval(connectionId, planId); load(); })} data-testid="suite-ask-approval">Ask for approval</Button> : null}
            <Button variant={report ? "primary" : "secondary"} disabled={!canRun} loading={busy === "run"} data-testid="suite-run"
              onClick={() => act("run", async () => { const r = await suiteApi.run(connectionId, planId); go({ run: r.id, plan: null, view: "run" }); })}>Run {ready} steps</Button>
          </div>
        } />
      <p><Link href="?">All plans</Link></p>
      {error ? <Status tone="danger">{error}</Status> : null}
      {p.order_errors.length ? <Status tone="danger">{p.order_errors.join(" ")}</Status> : null}
      {p.cannot_undo?.length ? <section className={styles.section}><h2>Not undone here</h2><ul className={styles.list}>{p.cannot_undo.map((c, i) => <li key={i}>{c}</li>)}</ul></section> : null}
      {report ? (
        <section className={styles.section} aria-label="Check result" data-testid="suite-check-report">
          <Status tone={report.can_apply ? "success" : "warning"}>
            {report.counts.ready} ready · {report.counts.no_change} nothing to change · {report.counts.needs_input} need input · {report.counts.blocked} blocked · {report.counts.waiting} waiting.
            {report.receipt ? ` Checked at ${new Date(report.checked_at).toLocaleTimeString()}; good for one hour for this exact plan.` : " Fix the steps above and check again."}
          </Status>
          {report.needs_approval ? <Status tone={approved ? "success" : "warning"}>{approved ? `Approved by ${p.approval?.decided_by ?? "a manager"}.` : pending ? `Waiting for approval, asked by ${p.approval?.requested_by ?? "you"}. Someone else approves it in Safety > Approvals.` : `This plan needs a manager's approval (accounting steps, or more than ${report.threshold} hard-to-undo records).`}</Status> : null}
        </section>
      ) : p.check ? <Status tone="warning">The plan changed after its last check. Check it again.</Status> : null}
      {report ? <CheckEveryVersion planId={planId} /> : null}
      <div className={styles.waves} data-testid="suite-waves">
        {p.waves.map((w, i) => (
          <section key={i} className={styles.wave} aria-label={`Wave ${i + 1}`}>
            <h3>Wave {i + 1}{byId.get(w[0])?.type === "install" ? " · installs" : ` · ${p.rank_labels[w[0]] ?? ""}`}</h3>
            <ul className={styles.list}>{w.map((sid) => { const s = byId.get(sid); return s ? <StepRow key={sid} s={s} report={report} /> : null; })}</ul>
          </section>
        ))}
      </div>
    </>
  );
}

function RunBoard({ runId }: { runId: string }) {
  const { connectionId } = useSuite();
  const { go } = useNav();
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  useTabBusy(busy !== null);
  useEffect(() => {
    let live = true;
    let t: ReturnType<typeof setTimeout> | undefined;
    const tick = () => suiteApi.getRun(connectionId, runId).then((r) => {
      if (!live) return;
      setRun(r);
      if (r.payload.state === "running" || r.payload.state === "queued") t = setTimeout(tick, 2000);
    }, (e: unknown) => live && setError(errText(e)));
    void tick();
    return () => { live = false; if (t) clearTimeout(t); };
  }, [connectionId, runId, busy]);
  if (error && !run) return <Status tone="danger">{error}</Status>;
  if (!run) return <Status tone="busy">Reading the run…</Status>;
  const p = run.payload;
  const all = p.waves.flatMap((w) => w.steps);
  const done = all.filter((s) => s.state === "done" || s.state === "no_change" || s.state === "skipped").length;
  const finished = !["running", "queued"].includes(p.state);
  async function act(name: string, fn: () => Promise<unknown>) {
    setBusy(name); setError(null);
    try { await fn(); } catch (e) { setError(errText(e)); } finally { setBusy(null); }
  }
  const STATE: Record<string, string> = { queued: "Starting", running: "Running", paused: "Paused: a step failed", stopped: "Stopped", done: "Finished", failed: "Did not run" };
  return (
    <>
      <PageHead title={run.name} purpose={`${p.kind === "undo" ? "Undo run" : "Setup run"} · ${done} of ${all.length} steps settled`}
        actions={
          <div className={styles.row}>
            {!finished || p.state === "paused" ? <Button variant="danger" loading={busy === "stop"} onClick={() => act("stop", () => suiteApi.stop(connectionId, runId))} data-testid="suite-stop">Stop</Button> : null}
            {p.state === "paused" ? <Button variant="primary" loading={busy === "carry"} onClick={() => act("carry", () => suiteApi.carryOn(connectionId, runId))} data-testid="suite-carry-on">Skip it and carry on</Button> : null}
            {finished && p.kind !== "undo" ? <Button loading={busy === "undo"} onClick={() => act("undo", async () => { const u = await suiteApi.undoPlan(connectionId, runId); go({ run: null, plan: u.id, view: "board" }); })} data-testid="suite-undo">Make the undo plan</Button> : null}
          </div>
        } />
      <p><Link href="?">All plans</Link> · <Link href={`?plan=${p.plan_id}&view=board`}>The plan</Link></p>
      <Status tone={p.state === "done" ? "success" : p.state === "paused" || p.state === "failed" ? "warning" : "busy"} aria-live="polite">{STATE[p.state] ?? p.state}{p.message ? `: ${p.message}` : ""}</Status>
      {error ? <Status tone="danger">{error}</Status> : null}
      <div className={styles.waves} data-testid="suite-run-board">
        {p.waves.map((w) => (
          <section key={w.n} className={styles.wave} aria-label={`Wave ${w.n}`}>
            <h3>Wave {w.n}</h3>
            <ul className={styles.list}>
              {w.steps.map((s) => (
                <li key={s.id} className={styles.step} data-state={s.state}>
                  <StateIcon state={s.state} />
                  <div><div>{s.label}</div><div className={styles.muted}>{STATE_WORD[s.state]}{s.message ? `: ${s.message}` : ""}</div></div>
                  <span />
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}
