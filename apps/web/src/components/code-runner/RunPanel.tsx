"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchApi } from "@/lib/api/client";
import { codeRunnerRunsApi as api, type CRChange, type CRRun } from "@/lib/api/code-runner";
import s from "./CodeRunner.module.css";

type View = "changes" | "results" | "console" | "profile";
const LIVE = new Set(["queued", "running", "paused", "stopping"]);
const sha256 = async (t: string) =>
  Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(t)))).map((b) => b.toString(16).padStart(2, "0")).join("");

/** Test run by default → receipt → (approval) → real run → undo. Every gate is enforced by the server. */
export function RunPanel({ connectionId, code, goToLine }: { connectionId: string; code: string; goToLine: (line: number) => void }) {
  const [run, setRun] = useState<CRRun | null>(null);
  const [receipt, setReceipt] = useState<CRRun | null>(null);
  const [hash, setHash] = useState("");
  const [view, setView] = useState<View>("changes");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { sha256(code).then(setHash); }, [code]);
  const poll = useCallback(async (runId: string) => {
    for (;;) {
      const r = await api.get(connectionId, runId);
      setRun(r);
      if (!LIVE.has(r.status)) { if (r.mode === "dry" && !r.estimate) setReceipt(r); return r; }
      await new Promise((ok) => setTimeout(ok, 700));
    }
  }, [connectionId]);
  const act = async (fn: () => Promise<{ id: string } | unknown>) => {
    setErr(""); setBusy(true);
    try {
      const out = await fn();
      if (out && typeof out === "object" && "id" in out) await poll((out as { id: string }).id);
    } catch (e) {
      const d = (e as { detail?: { message?: string } }).detail;
      setErr(d?.message ?? (e as Error).message);
    } finally { setBusy(false); }
  };
  const fresh = receipt && receipt.status === "done" && receipt.code_hash === hash;
  const needsApproval = !!receipt?.safety?.needs_approval && !receipt.approval?.approved;
  const live = run && LIVE.has(run.status);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <h3>Run</h3>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        <button className={`${s.btn} ${s.primary}`} disabled={busy} onClick={() => act(() => api.start(connectionId, { code }))}>Test run</button>
        <button className={s.btn} disabled={busy} onClick={() => act(() => api.start(connectionId, { code, sample: true }))}>Estimate</button>
        <button className={s.btn} disabled={busy || !fresh || needsApproval}
          title={!fresh ? "Test run this exact script first" : needsApproval ? "Needs an approver" : ""}
          onClick={() => confirm(`Run for real? ${receipt?.counts ? Object.entries(receipt.counts).map(([k, v]) => `${v} ${k}`).join(", ") : ""}`) &&
            act(() => api.start(connectionId, { code, mode: "real", receipt_id: receipt!.id }))}>Run for real</button>
        {fresh && needsApproval && <button className={s.btn} disabled={busy} onClick={() => act(async () => { await api.approve(connectionId, receipt!.id); setReceipt(await api.get(connectionId, receipt!.id)); })}>Approve</button>}
      </div>
      {live && run && (
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <progress max={run.progress?.total || 1} value={run.progress?.done || 0} style={{ flex: 1 }} aria-label="Progress" />
          <span className={s.muted}>{run.progress ? `${run.progress.done}/${run.progress.total}` : run.status}</span>
          {run.status === "paused"
            ? <button className={s.btn} onClick={() => api.control(connectionId, run.id, "resume")}>Resume</button>
            : <button className={s.btn} onClick={() => api.control(connectionId, run.id, "pause")}>Pause</button>}
          <button className={s.btn} onClick={() => api.control(connectionId, run.id, "stop")}>Stop</button>
        </div>
      )}
      {err && <p className={s.warn} role="alert">{err}</p>}
      {run && !live && <RunSummary run={run} connectionId={connectionId} goToLine={goToLine}
        onResume={() => act(() => api.resume(connectionId, run.id))}
        onUndo={async () => { const p = await api.undoPreview(connectionId, run.id); if (confirm(`Undo this run?\n\n${p.code.slice(0, 1200)}`)) await act(() => api.undo(connectionId, run.id)); }} />}
      {run && (
        <>
          <div role="tablist" className={s.tabs} style={{ padding: 0 }}>
            {(["changes", "results", "console", "profile"] as View[]).map((v) => (
              <button key={v} role="tab" className={s.tab} aria-selected={view === v} onClick={() => setView(v)}>
                {v === "changes" ? `Changes (${run.changes_total})` : v === "results" ? `Results (${run.results.length})` : v === "console" ? "Console" : "Profile"}
              </button>
            ))}
          </div>
          {view === "changes" && <Changes changes={run.changes} dry={run.mode === "dry"} />}
          {view === "results" && <Results rows={run.results} connectionId={connectionId} runId={run.id} />}
          {view === "console" && <Console run={run} goToLine={goToLine} />}
          {view === "profile" && <Profile run={run} goToLine={goToLine} />}
        </>
      )}
    </div>
  );
}

function RunSummary({ run, goToLine, onResume, onUndo }: { run: CRRun; connectionId: string; goToLine: (n: number) => void; onResume: () => void; onUndo: () => void }) {
  const sf = run.safety;
  return (
    <div className={s.note} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <strong>{run.mode === "dry" ? (run.estimate ? "Estimate" : "Test run") : run.undo_of ? "Undo" : "Real run"}: {run.status}</strong>
      {sf && <span data-level={sf.level}>Safety: <b>{sf.level}</b> — {sf.reasons.join(" ")}</span>}
      {!!sf?.money.length && <span className={s.warn}>Money guard: {sf.money.join(", ")}. An owner or admin must approve the real run.</span>}
      {run.approval?.approved && <span>Approved.</span>}
      {run.estimate && <span>About {run.estimate.seconds}s for {run.estimate.records} records, ~{run.estimate.writes} changes ({run.estimate.basis}).</span>}
      {run.error && (
        <button className={s.issue} data-sev="error" onClick={() => run.error?.line && goToLine(run.error.line)}>
          {run.error.line ? `Line ${run.error.line}: ` : ""}{run.error.message}{run.error.hint ? ` — ${run.error.hint}` : ""}
        </button>
      )}
      <div style={{ display: "flex", gap: 6 }}>
        {run.mode === "real" && (run.status === "failed" || run.status === "stopped") && <button className={s.btn} onClick={onResume}>Resume from where it stopped</button>}
        {run.mode === "real" && !run.undo_of && run.changes_total > 0 && <button className={s.btn} onClick={onUndo}>Undo</button>}
      </div>
    </div>
  );
}

const show = (v: unknown) => (v === null || v === undefined ? "—" : Array.isArray(v) && v.length === 2 && typeof v[0] === "number" ? String(v[1]) : typeof v === "object" ? JSON.stringify(v) : String(v));

function Changes({ changes, dry }: { changes: CRChange[]; dry: boolean }) {
  if (!changes.length) return <p className={s.muted}>No records {dry ? "would change" : "changed"}.</p>;
  return (
    <table className={s.table}>
      <thead><tr><th>What</th><th>Record</th><th>Before</th><th>After</th></tr></thead>
      <tbody>
        {changes.slice(0, 500).map((c, i) => {
          const keys = Object.keys({ ...(c.before ?? {}), ...(c.after ?? {}) }).filter((k) => k !== "id" && k !== "display_name");
          const rec = c.url ? <a href={c.url} target="_blank" rel="noreferrer">{c.label || `${c.model} ${c.id}`}</a> : `${c.model} ${c.id && c.id > 0 ? c.id : "(new)"}`;
          return (
            <tr key={i}>
              <td>{c.op === "method" ? c.method : c.op}</td><td>{rec}</td>
              <td>{c.op === "write" ? keys.map((k) => <div key={k}>{k}: {show(c.before?.[k])}</div>) : c.op === "unlink" ? "exists" : "—"}</td>
              <td>{c.op === "unlink" ? "deleted" : keys.map((k) => <div key={k}>{k}: {show(c.after?.[k])}</div>)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Results({ rows, connectionId, runId }: { rows: Record<string, unknown>[]; connectionId: string; runId: string }) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<{ col: string; dir: 1 | -1 } | null>(null);
  const [mode, setMode] = useState<"table" | "chart" | "json">("table");
  const cols = useMemo(() => Array.from(new Set(rows.flatMap((r) => Object.keys(r)))), [rows]);
  const num = cols.find((c) => rows.every((r) => typeof r[c] === "number" || r[c] == null) && c !== "id");
  const shown = useMemo(() => {
    const f = q ? rows.filter((r) => JSON.stringify(r).toLowerCase().includes(q.toLowerCase())) : rows;
    return sort ? [...f].sort((a, b) => (String(a[sort.col] ?? "") > String(b[sort.col] ?? "") ? sort.dir : -sort.dir)) : f;
  }, [rows, q, sort]);
  const download = async (fmt: "csv" | "json") => {
    const res = await fetchApi(api.exportUrl(connectionId, runId, fmt));
    const url = URL.createObjectURL(await res.blob());
    const a = Object.assign(document.createElement("a"), { href: url, download: `run-${runId.slice(0, 8)}.${fmt}` });
    a.click(); URL.revokeObjectURL(url);
  };
  if (!rows.length) return <p className={s.muted}>Call result(rows) in your script to see a table here.</p>;
  const max = num ? Math.max(1, ...shown.map((r) => Number(r[num]) || 0)) : 1;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", gap: 6 }}>
        <input className={s.input} placeholder="Filter" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filter results" />
        <select className={s.select} value={mode} onChange={(e) => setMode(e.target.value as typeof mode)} aria-label="Show as">
          <option value="table">Table</option>{num && <option value="chart">Chart</option>}<option value="json">JSON</option>
        </select>
        <button className={s.btn} onClick={() => download("csv")}>CSV</button>
        <button className={s.btn} onClick={() => download("json")}>JSON</button>
      </div>
      {mode === "json" && <pre style={{ maxBlockSize: 320, overflow: "auto", fontSize: "var(--text-xs)" }}>{JSON.stringify(shown.slice(0, 500), null, 2)}</pre>}
      {mode === "chart" && num && (
        <div role="img" aria-label={`Bar chart of ${num}`}>
          {shown.slice(0, 40).map((r, i) => (
            <div key={i} style={{ display: "grid", gridTemplateColumns: "120px 1fr 60px", gap: 6, alignItems: "center", fontSize: "var(--text-xs)" }}>
              <span>{show(r[cols.find((c) => c !== num) ?? "id"])}</span>
              <span style={{ blockSize: 10, inlineSize: `${(Number(r[num]) / max) * 100}%`, background: "var(--accent)", borderRadius: 2 }} />
              <span>{show(r[num])}</span>
            </div>
          ))}
        </div>
      )}
      {mode === "table" && (
        <table className={s.table}>
          <thead><tr>{cols.map((c) => (
            <th key={c}><button className={s.close} onClick={() => setSort({ col: c, dir: sort?.col === c && sort.dir === 1 ? -1 : 1 })}>
              {c}{sort?.col === c ? (sort.dir === 1 ? " ▲" : " ▼") : ""}</button></th>
          ))}</tr></thead>
          <tbody>{shown.slice(0, 500).map((r, i) => <tr key={i}>{cols.map((c) => <td key={c}>{show(r[c])}</td>)}</tr>)}</tbody>
        </table>
      )}
    </div>
  );
}

function Console({ run, goToLine }: { run: CRRun; goToLine: (n: number) => void }) {
  const groups = useMemo(() => {
    const g = new Map<string, typeof run.events>();
    for (const e of run.events.filter((x) => x.t !== "progress")) {
      const k = e.t === "error" ? "Errors" : e.group || "Log";
      g.set(k, [...(g.get(k) ?? []), e]);
    }
    return [...g.entries()];
  }, [run]);
  return (
    <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}>
      <p className={s.muted}>{run.calls_total} Odoo calls · {run.timing_ms ?? "—"} ms (database query counts aren&apos;t available over Odoo&apos;s API)</p>
      {groups.map(([name, evs]) => (
        <details key={name} open>
          <summary>{name} ({evs.length})</summary>
          {evs.map((e, i) => (
            <button key={i} className={s.issue} data-sev={e.t === "error" ? "error" : undefined} onClick={() => e.line && goToLine(e.line)}>
              {e.line ? `L${e.line} ` : ""}{e.msg ?? `${e.message}${e.hint ? ` — ${e.hint}` : ""}`}
            </button>
          ))}
        </details>
      ))}
    </div>
  );
}

function Profile({ run, goToLine }: { run: CRRun; goToLine: (n: number) => void }) {
  const p = run.profile;
  if (!p) return <p className={s.muted}>No profile yet.</p>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {p.fixes.map((f, i) => <button key={i} className={s.issue} data-sev="warning" onClick={() => goToLine(f.line)}>Line {f.line}: {f.fix}</button>)}
      <table className={s.table}>
        <thead><tr><th>Line</th><th>Calls</th><th>ms</th><th>Code</th></tr></thead>
        <tbody>{p.lines.map((l) => (
          <tr key={l.line}><td><button className={s.close} onClick={() => goToLine(l.line)}>{l.line}</button></td><td>{l.calls}</td><td>{l.ms}</td><td title={l.methods.join(", ")}>{l.source}</td></tr>
        ))}</tbody>
      </table>
    </div>
  );
}
