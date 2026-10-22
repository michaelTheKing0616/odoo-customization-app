"use client";

/* Code runner R3 screens: library (versions, diff, comments, share, tests, params), live co-edit,
   starter gallery, notebooks, promote, audit, secrets vault, AI settings. Every gate is server-side. */
import { flushSync } from "react-dom";
import { morphInPlace } from "@/lib/morph";
import { optimistic } from "@/lib/optimistic";
import { toast } from "sonner";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  codeRunnerLibraryApi as lib, codeRunnerOpsApi as ops, codeRunnerRunsApi as runs,
  type CRAuditItem, type CRCell, type CRParam, type CRPromotion, type CRRunbookStep, type CRRunSummary, type CRScript,
  type CRScriptSummary, type CRSecret, type CRSettings, type CRShareCheck, type CRStarter, type CRTest, type CRTestResult,
} from "@/lib/api/code-runner";
import { connectionsApi } from "@/lib/api/connections";
import type { Connection } from "@/lib/api/types-schema";
import s from "./CodeRunner.module.css";
import { Term } from "@/components/ui/Term";

export type LinkedTab = { id: string; name: string; code: string; sid?: string; rev?: number; kind?: "script" | "notebook"; cells?: CRCell[] };
const when = (t?: number | null) => (t ? new Date(t * 1000).toLocaleString() : "");
const msg = (e: unknown) => (e instanceof Error ? e.message : String(e));
const newCell = (type: CRCell["type"] = "code"): CRCell => ({ id: Math.random().toString(36).slice(2, 9), type, source: "" });

function useAsync() {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true); setErr("");
    try { return await fn(); } catch (e) { setErr(msg(e)); return undefined; } finally { setBusy(false); }
  }, []);
  return { busy, err, run, setErr };
}
const Err = ({ text }: { text: string }) => (text ? <p className={s.warn} role="alert">{text}</p> : null);

/* ---------------------------------------------------------------- live co-edit (item 24) */
export function useLiveScript(connectionId: string, tab: LinkedTab, apply: (patch: Partial<LinkedTab>) => void, cursorLine?: number) {
  const [editors, setEditors] = useState<{ who: string; line: number | null }[]>([]);
  const [conflict, setConflict] = useState(false);
  const sent = useRef<string>(tab.code);
  const sentCells = useRef<string>(JSON.stringify(tab.cells ?? []));
  const dirty = tab.code !== sent.current || JSON.stringify(tab.cells ?? []) !== sentCells.current;
  useEffect(() => { sent.current = tab.code; sentCells.current = JSON.stringify(tab.cells ?? []); setConflict(false); }, [tab.sid]); // eslint-disable-line react-hooks/exhaustive-deps
  // push local edits (debounced) against the revision we last saw; the server refuses a stale base (409)
  useEffect(() => {
    if (!tab.sid || !dirty || conflict) return;
    const t = setTimeout(async () => {
      try {
        const out = await lib.livePut(connectionId, tab.sid!, { base_rev: tab.rev ?? 0, code: tab.code, cells: tab.cells });
        sent.current = tab.code;
        sentCells.current = JSON.stringify(tab.cells ?? []);
        apply({ rev: out.rev });
      } catch (e) {
        if ((e as { status?: number }).status === 409) setConflict(true);  // stale base: someone saved first
        // other failures (offline, 5xx): keep the edit local; the next change retries
      }
    }, 1200);
    return () => clearTimeout(t);
  }, [tab.code, tab.cells, tab.sid, dirty, conflict]); // eslint-disable-line react-hooks/exhaustive-deps
  // pull others' edits only when nothing local is unsent
  useEffect(() => {
    if (!tab.sid) return;
    let gone = false;
    const tick = async () => {
      try {
        const live = await lib.liveGet(connectionId, tab.sid!, cursorLine);
        if (gone) return;
        setEditors(live.editors ?? []);
        if (live.rev > (tab.rev ?? 0) && !dirty) {
          sent.current = live.code;
          sentCells.current = JSON.stringify(live.cells ?? []);
          apply({ code: live.code, rev: live.rev, cells: live.cells });
        }
      } catch { /* offline: keep editing locally */ }
    };
    tick();
    const t = setInterval(tick, 4000);
    return () => { gone = true; clearInterval(t); };
  }, [tab.sid, tab.rev, dirty, cursorLine]); // eslint-disable-line react-hooks/exhaustive-deps
  const takeTheirs = async () => {
    const live = await lib.liveGet(connectionId, tab.sid!);
    sent.current = live.code;
    sentCells.current = JSON.stringify(live.cells ?? []);
    apply({ code: live.code, rev: live.rev, cells: live.cells });
    setConflict(false);
  };
  const keepMine = async () => {
    const live = await lib.liveGet(connectionId, tab.sid!);
    apply({ rev: live.rev });  // next push is based on their revision and saves over it
    setConflict(false);
  };
  return { editors, conflict, dirty, takeTheirs, keepMine };
}

export function LiveBar({ live }: { live: ReturnType<typeof useLiveScript> }) {
  return (
    <>
      {live.editors.length > 1 && (
        <p className={s.note} aria-live="polite">Editing now: {live.editors.map((e) => `${e.who}${e.line ? ` (line ${e.line})` : ""}`).join(", ")}</p>
      )}
      {live.conflict && (
        <div className={s.warn} role="alert">
          Someone else saved a newer version while you were typing. Your change wasn&apos;t saved.
          <div style={{ display: "flex", gap: 8, marginBlockStart: 6 }}>
            <button className={s.btn} onClick={live.takeTheirs}>Load their version</button>
            <button className={s.btn} onClick={live.keepMine}>Keep mine and save over it</button>
          </div>
        </div>
      )}
    </>
  );
}

/* ---------------------------------------------------------------- params form (item 21) */
export function ParamsForm({ fields, values, onChange }: { fields: CRParam[]; values: Record<string, unknown>; onChange: (v: Record<string, unknown>) => void }) {
  if (!fields.length) return <p className={s.muted}>This script has no settings. Use params.get(&quot;name&quot;, default) to add some.</p>;
  return (
    <div style={{ display: "grid", gap: 6 }}>
      {fields.map((f) => {
        const v = values[f.name] ?? f.default ?? "";
        const id = `crp-${f.name}`;
        return (
          <label key={f.name} htmlFor={id} style={{ display: "grid", gap: 2 }}>
            <span>{f.label}{f.required ? " *" : ""} <span className={s.muted}>({f.type})</span></span>
            {f.type === "bool" ? (
              <input id={id} type="checkbox" checked={!!v} onChange={(e) => onChange({ ...values, [f.name]: e.target.checked })} />
            ) : (
              <input id={id} className={s.input} type={f.type === "date" ? "date" : f.type === "number" || f.type === "id" ? "number" : "text"}
                value={String(v)} required={f.required} placeholder={f.type === "ids" ? "1, 2, 3" : undefined}
                onChange={(e) => onChange({ ...values, [f.name]: e.target.value })} />
            )}
          </label>
        );
      })}
    </div>
  );
}

/* ---------------------------------------------------------------- library (items 19, 21, 22, 27) */
export function LibraryPanel({ connectionId, tab, onOpen, onLinked, goToLine }: {
  connectionId: string; tab: LinkedTab; onOpen: (sc: CRScript) => void; onLinked: (patch: Partial<LinkedTab>) => void; goToLine: (n: number) => void;
}) {
  const a = useAsync();
  const [query, setQuery] = useState("");
  const [folder, setFolder] = useState("");
  const [list, setList] = useState<{ scripts: CRScriptSummary[]; folders: string[] }>({ scripts: [], folders: [] });
  const [script, setScript] = useState<CRScript | null>(null);
  const load = useCallback(() => a.run(async () => setList(await lib.search(connectionId, { q: query, folder }))), [connectionId, query, folder]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);
  const refresh = useCallback(async () => { if (tab.sid) setScript(await lib.get(connectionId, tab.sid)); }, [connectionId, tab.sid]);
  useEffect(() => { setScript(null); if (tab.sid) a.run(refresh); }, [tab.sid]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = () => a.run(async () => {
    const name = prompt("Name for this script", tab.name.replace(/\.py$/, ""));
    if (!name) return;
    const f = prompt("Folder (optional)", folder) ?? "";
    const out = await lib.create(connectionId, { name, code: tab.code, folder: f, kind: tab.kind ?? "script", cells: tab.cells });
    onLinked({ sid: out.id, rev: out.rev, name: `${out.name}.py`, kind: out.kind });
    await load();
  });

  return (
    <>
      <h3>Script library</h3>
      <Err text={a.err} />
      {!tab.sid && <button className={`${s.btn} ${s.primary}`} onClick={save} disabled={a.busy}>Save this tab to the library</button>}
      <div style={{ display: "flex", gap: 6 }}>
        <input className={s.input} aria-label="Search scripts" placeholder="Search name, tag or code" value={query} onChange={(e) => setQuery(e.target.value)} />
        <select className={s.select} aria-label="Folder" value={folder} onChange={(e) => setFolder(e.target.value)}>
          <option value="">All folders</option>
          {list.folders.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
      </div>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 4 }}>
        {list.scripts.map((x) => (
          <li key={x.id}>
            <button className={s.issue} onClick={(e) => { const el = e.currentTarget as HTMLElement; void a.run(async () => { const sc = await lib.get(connectionId, x.id); morphInPlace(el, () => flushSync(() => onOpen(sc)), ".cr-editors-host"); }); }} aria-current={x.id === tab.sid ? "true" : undefined}>
              <strong>{x.name}</strong> <span className={s.muted}>{x.kind === "notebook" ? "notebook · " : ""}{x.folder ? `${x.folder} · ` : ""}v{x.versions}
                {x.open_comments ? ` · ${x.open_comments} open comments` : ""} · {when(x.updated_at)}</span>
            </button>
          </li>
        ))}
        {!list.scripts.length && <li className={s.muted}>No saved scripts yet.</li>}
      </ul>
      {script && <ScriptDetail connectionId={connectionId} script={script} tab={tab} refresh={refresh} onLinked={onLinked} goToLine={goToLine} />}
    </>
  );
}

function ScriptDetail({ connectionId, script, tab, refresh, onLinked, goToLine }: {
  connectionId: string; script: CRScript; tab: LinkedTab; refresh: () => Promise<void>; onLinked: (p: Partial<LinkedTab>) => void; goToLine: (n: number) => void;
}) {
  const a = useAsync();
  const [diff, setDiff] = useState("");
  const [line, setLine] = useState(1);
  const [text, setText] = useState("");
  const [conns, setConns] = useState<Connection[]>([]);
  const [pick, setPick] = useState<string[]>([]);
  const [checks, setChecks] = useState<CRShareCheck[] | null>(null);
  const [testRes, setTestRes] = useState<{ results: CRTestResult[]; passed: boolean } | null>(null);
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [paramErr, setParamErr] = useState<string[]>([]);
  const [tests, setTestsLocal] = useState<CRTest[]>(script.tests.length ? script.tests : [{ name: "Runs without errors", expect: { no_error: true } }]);
  useEffect(() => { connectionsApi.listConnections().then((c) => setConns(c.filter((x) => x.id !== connectionId))).catch(() => setConns([])); }, [connectionId]);
  const editTest = (i: number, t: CRTest) => setTestsLocal(tests.map((x, j) => (j === i ? t : x)));
  const saveTests = (t: CRTest[] = tests) => { const prev = tests; void optimistic({ what: "the tests", apply: () => setTestsLocal(t), commit: async () => { await lib.meta(connectionId, script.id, { tests: t }); await refresh(); }, rollback: () => setTestsLocal(prev), onRolledBack: (m) => toast.error(m) }); };
  const num = (t: CRTest, k: string) => (t.expect[k] as number | undefined) ?? "";

  return (
    <section aria-label={`Script ${script.name}`} style={{ display: "grid", gap: 10 }}>
      <Err text={a.err} />
      <details open>
        <summary>Versions ({script.version_list.length})</summary>
        <button className={s.btn} disabled={a.busy} onClick={() => a.run(async () => {
          const note = prompt("What changed? (optional)") ?? ""; await lib.saveVersion(connectionId, script.id, note); await refresh();
        })}>Save a version</button>
        <ul style={{ listStyle: "none", padding: 0 }}>
          {[...script.version_list].reverse().map((v) => (
            <li key={v.n} style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
              <span>v{v.n} · {when(v.at)}{v.note ? ` · ${v.note}` : ""}</span>
              <button className={s.btn} onClick={() => a.run(async () => setDiff((await lib.diff(connectionId, script.id, v.n)).diff || "No differences."))}>Compare with now</button>
              <button className={s.btn} onClick={() => confirm(`Replace the current code with version ${v.n}? The current code stays in the history.`) &&
                a.run(async () => { const out = await lib.restore(connectionId, script.id, v.n); onLinked({ code: out.code, rev: out.rev, cells: out.cells }); await refresh(); })}>Restore</button>
            </li>
          ))}
        </ul>
        {diff && <pre className={s.note} style={{ whiteSpace: "pre-wrap", fontFamily: "var(--font-mono)", maxBlockSize: 260, overflow: "auto" }} aria-label="Differences">{diff}</pre>}
      </details>

      <details>
        <summary>Comments ({script.comments.filter((c) => !c.resolved).length} open)</summary>
        {script.comments.map((c) => (
          <div key={c.id} className={s.note} style={{ opacity: c.resolved ? 0.6 : 1 }}>
            <button className={s.issue} onClick={() => goToLine(c.line)}>Line {c.line}</button> <strong>{c.by}</strong>: {c.text}
            {(c.replies ?? []).map((r, i) => <div key={i} style={{ paddingInlineStart: 12 }}>↳ <strong>{r.by}</strong>: {r.text}</div>)}
            <div style={{ display: "flex", gap: 6 }}>
              <button className={s.btn} onClick={() => { const r = prompt("Reply"); if (r) a.run(async () => { await lib.resolveComment(connectionId, script.id, c.id, { reply: r }); await refresh(); }); }}>Reply</button>
              <button className={s.btn} onClick={() => a.run(async () => { await lib.resolveComment(connectionId, script.id, c.id, { resolved: !c.resolved }); await refresh(); })}>
                {c.resolved ? "Reopen" : "Resolve"}</button>
            </div>
          </div>
        ))}
        <div style={{ display: "flex", gap: 6 }}>
          <input className={s.input} style={{ inlineSize: 70 }} type="number" min={1} aria-label="Line" value={line} onChange={(e) => setLine(Number(e.target.value) || 1)} />
          <input className={s.input} aria-label="Comment" placeholder="Comment on this line" value={text} onChange={(e) => setText(e.target.value)} />
          <button className={s.btn} disabled={!text.trim()} onClick={() => a.run(async () => { await lib.comment(connectionId, script.id, line, text); setText(""); await refresh(); })}>Add</button>
        </div>
      </details>

      <details>
        <summary>Settings form ({script.params.length})</summary>
        <ParamsForm fields={script.params} values={params} onChange={setParams} />
        {script.params.length > 0 && <button className={s.btn} onClick={() => a.run(async () => setParamErr((await lib.params(connectionId, tab.code, params)).errors))}>Check values</button>}
        {paramErr.map((e) => <p key={e} className={s.warn}>{e}</p>)}
      </details>

      <details>
        <summary>Share with other databases</summary>
        <p className={s.muted}>Each database is checked against its own models and Odoo version before it gets the script.</p>
        {conns.map((c) => (
          <label key={c.id} style={{ display: "flex", gap: 6 }}>
            <input type="checkbox" checked={pick.includes(c.id)} onChange={(e) => setPick(e.target.checked ? [...pick, c.id] : pick.filter((x) => x !== c.id))} />
            {c.name}{script.shared_connections?.includes(c.id) ? " (shared)" : ""}
          </label>
        ))}
        <button className={s.btn} disabled={!pick.length || a.busy} onClick={() => a.run(async () => { setChecks((await lib.share(connectionId, script.id, pick)).checks); await refresh(); })}>Check and share</button>
        {checks?.map((c) => (
          <p key={c.connection_id} className={c.ok ? s.note : s.warn}>{c.name ?? c.connection_id}{c.major ? ` (Odoo ${c.major})` : ""}: {c.ok ? "shared" : "not shared"}
            {[...c.errors, ...(c.warnings ?? [])].map((x) => <span key={x} style={{ display: "block" }}>{x}</span>)}</p>
        ))}
      </details>

      <details>
        <summary>Tests</summary>
        <p className={s.muted}>Tests run on a throwaway copy of this database, which is deleted afterwards. Nothing reaches the real data.</p>
        {tests.map((t, i) => (
          <div key={i} className={s.note} style={{ display: "grid", gap: 4 }}>
            <input className={s.input} aria-label="Test name" value={t.name} onChange={(e) => editTest(i, { ...t, name: e.target.value })} />
            {([["max_changes", "At most changes"], ["min_changes", "At least changes"], ["min_rows", "At least rows"]] as const).map(([k, lab]) => (
              <label key={k} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <span style={{ inlineSize: 120 }}>{lab}</span>
                <input className={s.input} type="number" min={0} value={num(t, k)}
                  onChange={(e) => { const ex = { ...t.expect }; if (e.target.value === "") delete ex[k]; else ex[k] = Number(e.target.value); editTest(i, { ...t, expect: ex }); }} />
              </label>
            ))}
            <input className={s.input} aria-label="Log must contain" placeholder="Log must contain…" value={(t.expect.log_contains as string | undefined) ?? ""}
              onChange={(e) => { const ex = { ...t.expect }; if (e.target.value) ex.log_contains = e.target.value; else delete ex.log_contains; editTest(i, { ...t, expect: ex }); }} />
            <button className={s.btn} onClick={() => saveTests(tests.filter((_, j) => j !== i))}>Remove test</button>
          </div>
        ))}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <button className={s.btn} onClick={() => setTestsLocal([...tests, { name: `Test ${tests.length + 1}`, expect: { no_error: true } }])}>Add test</button>
          <button className={s.btn} disabled={a.busy} onClick={() => saveTests()}>Save tests</button>
          <button className={`${s.btn} ${s.primary}`} disabled={a.busy} onClick={() => a.run(async () => { await lib.meta(connectionId, script.id, { tests }); setTestRes(await lib.runTests(connectionId, script.id)); })}>
            {a.busy ? "Running…" : "Run tests"}</button>
        </div>
        {testRes && (
          <div aria-live="polite">
            <p className={testRes.passed ? s.note : s.warn}>{testRes.passed ? "All tests passed." : "Some tests failed."}</p>
            {testRes.results.map((r) => (
              <p key={r.name}>{r.passed ? "✓" : "✗"} {r.name} <span className={s.muted}>({r.where === "copy" ? "on a copy" : r.where === "dry_run" ? "as a test run: no copy allowed" : r.where})</span>
                {r.failures.map((f) => <span key={f} style={{ display: "block" }} className={s.muted}>{f}</span>)}</p>
            ))}
          </div>
        )}
      </details>

      <button className={s.btn} onClick={() => confirm(`Delete "${script.name}" from the library?`) && a.run(async () => { await lib.remove(connectionId, script.id); onLinked({ sid: undefined, rev: undefined }); })}>
        Delete from library</button>
    </section>
  );
}

/* ---------------------------------------------------------------- gallery (item 23) */
export function GalleryPanel({ connectionId, onUse }: { connectionId: string; onUse: (name: string, code: string) => void }) {
  const a = useAsync();
  const [items, setItems] = useState<CRStarter[]>([]);
  useEffect(() => { a.run(async () => setItems((await lib.gallery(connectionId)).starters)); }, [connectionId]); // eslint-disable-line react-hooks/exhaustive-deps
  const cats = [...new Set(items.map((i) => i.category))];
  return (
    <>
      <h3>Starter scripts</h3>
      <Err text={a.err} />
      {cats.map((c) => (
        <section key={c} aria-label={c}>
          <h4 style={{ margin: "6px 0" }}>{c}</h4>
          {items.filter((i) => i.category === c).map((i) => (
            <div key={i.id} className={s.note} style={{ marginBlockEnd: 6 }}>
              <strong>{i.title}</strong> <span className={i.risk === "writes" ? s.warn : s.muted} style={{ padding: "0 4px" }}>{i.risk === "writes" ? "changes data" : "read only"}</span>
              {i.params.length > 0 && <p className={s.muted} style={{ margin: "4px 0" }}>Settings: {i.params.map((p) => p.label).join(", ")}</p>}
              <button className={s.btn} onClick={() => onUse(i.title, i.code)}>Open in a new tab</button>
            </div>
          ))}
        </section>
      ))}
    </>
  );
}

/* ---------------------------------------------------------------- notebooks / runbooks (item 26) */
export function NotebookPanel({ connectionId, tab, onLinked, onCreate }: {
  connectionId: string; tab: LinkedTab; onLinked: (p: Partial<LinkedTab>) => void; onCreate: (sc: CRScript) => void;
}) {
  const a = useAsync();
  const [steps, setSteps] = useState<CRRunbookStep[] | null>(null);
  const [dry, setDry] = useState<Record<string, string>>({});
  const cells = tab.cells ?? [];
  if (tab.kind !== "notebook" || !tab.sid) {
    return (
      <>
        <h3>Notebooks</h3>
        <p className={s.muted}>A notebook is a list of steps with notes in between. Steps run in order and stop at the first one that fails.</p>
        <Err text={a.err} />
        <button className={s.btn} onClick={() => a.run(async () => {
          const name = prompt("Notebook name"); if (!name) return;
          const created = await lib.create(connectionId, { name, code: "", kind: "notebook", cells: [{ ...newCell("markdown"), source: "What this runbook does" }, newCell()] });
          onCreate(await lib.get(connectionId, created.id));
        })}>New notebook</button>
      </>
    );
  }
  const setCells = (c: CRCell[]) => { setDry({}); onLinked({ cells: c, code: c.filter((x) => x.type === "code").map((x) => x.source).join("\n\n") }); };
  const runAll = (mode: "dry" | "real") => a.run(async () => {
    const out = await lib.runbook(connectionId, tab.sid!, { mode, receipts: mode === "real" ? dry : {} });
    setSteps(out.steps);
    if (mode === "dry") setDry(Object.fromEntries(out.steps.filter((x) => x.status === "done" && x.run_id).map((x) => [x.cell, x.run_id!])));
  });
  const codeCells = cells.filter((c) => c.type === "code");
  const allDry = codeCells.length > 0 && codeCells.every((c) => dry[c.id]);
  return (
    <>
      <h3>Notebook</h3>
      <Err text={a.err} />
      {cells.map((c, i) => {
        const st = steps?.find((x) => x.cell === c.id);
        return (
          <div key={c.id} className={s.note} style={{ display: "grid", gap: 4 }}>
            <span className={s.muted}>{c.type === "code" ? `Step ${codeCells.indexOf(c) + 1}` : "Note"}{st ? ` · ${st.status}` : ""}</span>
            <textarea className={s.input} rows={c.type === "code" ? 6 : 2} aria-label={c.type === "code" ? "Step code" : "Note"}
              style={{ fontFamily: c.type === "code" ? "var(--font-mono)" : undefined }} value={c.source}
              onChange={(e) => setCells(cells.map((x, j) => (j === i ? { ...c, source: e.target.value } : x)))} />
            {st?.message && <span className={s.warn}>{st.message}</span>}
            <button className={s.btn} onClick={() => setCells(cells.filter((x) => x.id !== c.id))}>Remove</button>
          </div>
        );
      })}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <button className={s.btn} onClick={() => setCells([...cells, newCell()])}>Add step</button>
        <button className={s.btn} onClick={() => setCells([...cells, newCell("markdown")])}>Add note</button>
        <button className={`${s.btn} ${s.primary}`} disabled={a.busy} onClick={() => runAll("dry")}>Test run all steps</button>
        <button className={s.btn} disabled={a.busy || !allDry} title={allDry ? undefined : "Test run every step first"}
          onClick={() => confirm("Run every step for real, in order? Each step uses its own test run as proof.") && runAll("real")}>Run all for real</button>
      </div>
    </>
  );
}

/* ---------------------------------------------------------------- promote (item 20) */
export function PromotePanel({ connectionId, tab }: { connectionId: string; tab: LinkedTab }) {
  const a = useAsync();
  const [check, setCheck] = useState<{ ok: boolean; reasons: string[] } | null>(null);
  const [items, setItems] = useState<CRPromotion[]>([]);
  const [receipts, setReceipts] = useState<CRRunSummary[]>([]);
  const [form, setForm] = useState({ kind: "cron" as "cron" | "action" | "button", model: "res.partner", number: 1, type: "days", receipt: "" });
  const load = useCallback(async () => {
    setItems((await ops.promotions(connectionId)).promotions);
    const r = (await runs.list(connectionId)).runs.filter((x) => x.mode === "dry" && x.status === "done");
    setReceipts(r);
    setForm((f) => ({ ...f, receipt: f.receipt || r[0]?.id || "" }));
  }, [connectionId]);
  useEffect(() => { a.run(load); }, [load]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const t = setTimeout(() => ops.promoteCheck(connectionId, tab.code).then(setCheck).catch(() => setCheck(null)), 400); return () => clearTimeout(t); }, [connectionId, tab.code]);
  const act = (pid: string, action: "run-once" | "publish" | "remove", text: string) => { if (confirm(text)) a.run(async () => { await ops.promotionAction(connectionId, pid, action); await load(); }); };
  return (
    <>
      <h3>Make it part of Odoo</h3>
      <p className={s.muted}>Turns this script into a <Term tech="ir.cron">scheduled job</Term> or an action inside Odoo. It is created switched off so you can test it, then you publish it.</p>
      <Err text={a.err} />
      {check && !check.ok && <div className={s.warn}>This script can&apos;t run inside Odoo yet:{check.reasons.map((r) => <span key={r} style={{ display: "block" }}>{r}</span>)}</div>}
      <label>Type <select className={s.select} value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as typeof form.kind })}>
        <option value="cron">Scheduled job</option><option value="action">Action menu</option><option value="button">Button</option></select></label>
      {form.kind !== "cron"
        ? <label>On model <input className={s.input} value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} /></label>
        : <label style={{ display: "flex", gap: 6, alignItems: "center" }}>Every
            <input className={s.input} style={{ inlineSize: 70 }} type="number" min={1} value={form.number} onChange={(e) => setForm({ ...form, number: Number(e.target.value) || 1 })} />
            <select className={s.select} value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              {["minutes", "hours", "days", "weeks", "months"].map((t) => <option key={t}>{t}</option>)}</select></label>}
      <label>Proof: a finished test run of this exact code
        <select className={s.select} value={form.receipt} onChange={(e) => setForm({ ...form, receipt: e.target.value })}>
          <option value="">Choose a dry run…</option>
          {receipts.map((r) => <option key={r.id} value={r.id}>{r.name || "Test run"} · {when(r.created_at)}</option>)}
        </select></label>
      <button className={`${s.btn} ${s.primary}`} disabled={a.busy || !form.receipt || (check ? !check.ok : false)} onClick={() => a.run(async () => {
        await ops.promote(connectionId, { script_id: tab.sid ?? null, name: tab.name.replace(/\.py$/, ""), code: tab.code, kind: form.kind,
          model: form.model, interval: form.kind === "cron" ? { number: form.number, type: form.type } : null, receipt_id: form.receipt });
        await load();
      })}>Create (switched off) for testing</button>
      {items.map((p) => (
        <div key={p.id} className={s.note}>
          <strong>{p.name}</strong> <span className={s.muted}>{p.kind === "cron" ? `every ${p.interval?.number ?? 1} ${p.interval?.type ?? "days"}` : `on ${p.model}`} · {p.status}</span>
          <div style={{ display: "flex", gap: 6, marginBlockStart: 4 }}>
            {p.status === "testing" && <button className={s.btn} onClick={() => act(p.id, "run-once", `Run "${p.name}" once now inside Odoo?`)}>Run once</button>}
            {p.status === "testing" && <button className={s.btn} onClick={() => act(p.id, "publish", `Publish "${p.name}"? It will start running on its own.`)}>Publish</button>}
            {p.status !== "removed" && <button className={s.btn} onClick={() => act(p.id, "remove", `Remove "${p.name}" from Odoo?`)}>Remove</button>}
          </div>
        </div>
      ))}
    </>
  );
}

/* ---------------------------------------------------------------- audit (item 25) */
export function AuditPanel({ connectionId }: { connectionId: string }) {
  const a = useAsync();
  const [items, setItems] = useState<CRAuditItem[]>([]);
  const load = useCallback(async () => setItems((await ops.audit(connectionId)).items), [connectionId]);
  useEffect(() => { a.run(load); }, [load]); // eslint-disable-line react-hooks/exhaustive-deps
  const undo = (it: CRAuditItem) => {
    if (!it.undo || !confirm("Undo this change?")) return;
    a.run(async () => {
      if (it.undo!.startsWith("runs/") && it.run_id) await runs.undo(connectionId, it.run_id);
      else if (it.undo!.startsWith("promotions/")) await ops.promotionAction(connectionId, String(it.promotion), "remove");
      await load();
    });
  };
  const label: Record<string, string> = { real_run: "Real run", undo: "Undo", runbook: "Notebook run", promotion_test: "Created in Odoo (off)",
    promotion_publish: "Published", "promotion_run-once": "Ran once in Odoo", promotion_remove: "Removed from Odoo", secret_set: "Secret saved",
    secret_deleted: "Secret deleted", ai_mode: "AI setting changed" };
  return (
    <>
      <h3>History</h3>
      <Err text={a.err} />
      <table className={s.table}>
        <thead><tr><th scope="col">When</th><th scope="col">What</th><th scope="col">Who</th><th scope="col"><span className="sr-only">Undo</span></th></tr></thead>
        <tbody>
          {items.map((it, i) => (
            <tr key={i}>
              <td>{when(it.at)}</td>
              <td>{label[it.kind] ?? it.kind}{it.name ? ` · ${it.name}` : ""}{it.counts ? ` · ${Object.entries(it.counts).map(([k, v]) => `${v} ${k}`).join(", ")}` : ""}{it.undone_by ? " · undone" : ""}</td>
              <td>{it.by ?? ""}</td>
              <td>{it.undo && <button className={s.btn} onClick={() => undo(it)} disabled={a.busy}>Undo</button>}</td>
            </tr>
          ))}
          {!items.length && <tr><td colSpan={4} className={s.muted}>Nothing has changed real data yet.</td></tr>}
        </tbody>
      </table>
    </>
  );
}

/* ---------------------------------------------------------------- vault (item 28) */
export function VaultPanel({ connectionId }: { connectionId: string }) {
  const a = useAsync();
  const [items, setItems] = useState<CRSecret[]>([]);
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [onlyHere, setOnlyHere] = useState(true);
  const load = useCallback(async () => setItems((await ops.vault(connectionId)).secrets), [connectionId]);
  useEffect(() => { a.run(load); }, [load]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <h3>Secrets</h3>
      <p className={s.muted}>Use a secret in a script with <code>secret(&quot;name&quot;)</code>. Values are stored encrypted, never shown again, and hidden in logs and results.</p>
      <Err text={a.err} />
      <ul style={{ listStyle: "none", padding: 0 }}>
        {items.map((x) => (
          <li key={x.name} style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <code>{x.name}</code><span className={s.muted}>{x.connections.length ? "this database only" : "all databases"} · {when(x.set_at)}</span>
            <button className={s.btn} onClick={() => { if (confirm(`Delete the secret "${x.name}"?`)) a.run(async () => { await ops.deleteSecret(connectionId, x.name); await load(); }); }}>Delete</button>
          </li>
        ))}
        {!items.length && <li className={s.muted}>No secrets yet.</li>}
      </ul>
      <form onSubmit={(e) => { e.preventDefault(); a.run(async () => {
        await ops.setSecret(connectionId, { name, value, connections: onlyHere ? [connectionId] : [] }); setName(""); setValue(""); await load(); }); }}
        style={{ display: "grid", gap: 6 }}>
        <input className={s.input} aria-label="Secret name" placeholder="Name, e.g. sms_api_key" value={name} onChange={(e) => setName(e.target.value)} required pattern="[A-Za-z_][A-Za-z0-9_]*" />
        <input className={s.input} aria-label="Secret value" type="password" autoComplete="new-password" placeholder="Value" value={value} onChange={(e) => setValue(e.target.value)} required />
        <label style={{ display: "flex", gap: 6 }}><input type="checkbox" checked={onlyHere} onChange={(e) => setOnlyHere(e.target.checked)} /> Only scripts on this database can use it</label>
        <button className={s.btn} disabled={a.busy}>Save secret</button>
      </form>
    </>
  );
}

/* ---------------------------------------------------------------- AI settings (item 29) */
export function SettingsPanel({ connectionId }: { connectionId: string }) {
  const a = useAsync();
  const [cur, setCur] = useState<CRSettings | null>(null);
  const [mode, setMode] = useState<"local" | "cloud">("local");
  const [consent, setConsent] = useState(false);
  useEffect(() => { a.run(async () => { const v = await ops.settings(connectionId); setCur(v); setMode(v.ai_mode); setConsent(!!v.consent); }); }, [connectionId]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <h3>AI assistant</h3>
      <Err text={a.err} />
      <fieldset style={{ border: 0, padding: 0, display: "grid", gap: 6 }}>
        <legend className={s.muted}>Where the assistant runs</legend>
        <label><input type="radio" name="crai" checked={mode === "local"} onChange={() => setMode("local")} /> On this computer (default). Your code stays here.</label>
        <label><input type="radio" name="crai" checked={mode === "cloud"} onChange={() => setMode("cloud")} /> Cloud AI. Better answers; your script text is sent to the AI provider.</label>
      </fieldset>
      {mode === "cloud" && (
        <label style={{ display: "flex", gap: 6 }}><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          I agree to send script text to the cloud AI provider. Secrets are never sent.</label>
      )}
      <button className={s.btn} disabled={a.busy || (mode === "cloud" && !consent)} onClick={() => a.run(async () => setCur(await ops.saveSettings(connectionId, { mode, consent })))}>Save</button>
      {cur?.consent && <p className={s.muted}>Cloud consent given by {cur.consent.by} on {when(cur.consent.by_at)}.</p>}
    </>
  );
}
