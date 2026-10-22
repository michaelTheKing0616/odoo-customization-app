"use client";

/* Bridge B6 + B10 screen: flows, canvas, versions (approve / roll out / roll back), monitor, record trace, export. */
import { TransitMap } from "./TransitMap";
import { HoldButton, Sparkline, WithTable } from "@/components/ui/craft";
import { markSuccess } from "@/components/ui/success";
import { useCallback, useEffect, useState } from "react";
import { bridgeFlowsApi as api, type BGCanvas, type BGFlowSummary, type BGMonitor } from "@/lib/api/bridge-gallery";
import { getApiBase } from "@/lib/api/client";
import s from "./Gallery.module.css";
import { FrameMeta } from "@/components/frame/FrameMeta";

const msg = (e: unknown) => (e instanceof Error ? e.message : String(e));
const STEPS = [5, 25, 50, 100];

function Canvas({ c }: { c: BGCanvas }) {
  const pos = Object.fromEntries(c.nodes.map((n) => [n.id, n]));
  return (
    <svg viewBox="0 0 900 280" role="img" aria-label="Flow canvas" style={{ inlineSize: "100%", blockSize: "auto" }}>
      {c.edges.map((e) => {
        const a = pos[e.from], b = pos[e.to];
        return a && b ? <line key={`${e.from}-${e.to}`} x1={a.x + 120} y1={a.y + 22} x2={b.x} y2={b.y + 22} stroke="var(--n6)" strokeWidth={2} markerEnd="url(#arr)" /> : null;
      })}
      <defs><marker id="arr" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="var(--n6)" /></marker></defs>
      {c.nodes.map((n) => (
        <g key={n.id} transform={`translate(${n.x},${n.y})`}>
          <rect width={120} height={44} rx={8} fill={n.kind === "guard" ? "var(--warning-subtle)" : "var(--surface)"} stroke={n.kind === "odoo" || n.kind === "connector" ? "var(--accent)" : "var(--border-subtle)"} />
          <text x={60} y={18} textAnchor="middle" fontSize={10} fill="var(--muted)">{n.kind}</text>
          <text x={60} y={34} textAnchor="middle" fontSize={12} fill="var(--ink)">{String(n.label ?? "").slice(0, 18)}</text>
        </g>
      ))}
    </svg>
  );
}

export function FlowsBoard() {
  const [flows, setFlows] = useState<BGFlowSummary[]>([]);
  const [sel, setSel] = useState<(BGFlowSummary & { monitor: BGMonitor }) | null>(null);
  const [canvas, setCanvas] = useState<BGCanvas | null>(null);
  const [key, setKey] = useState("");
  const [trace, setTrace] = useState<{ at: number; step: string; status: string; detail: string }[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [approverName, setApproverName] = useState("");
  const [err, setErr] = useState("");
  const run = useCallback(async <T,>(fn: () => Promise<T>) => {
    setBusy(true); setErr("");
    try { return await fn(); } catch (e) { setErr(msg(e)); return undefined; } finally { setBusy(false); }
  }, []);
  const reload = useCallback(() => run(async () => setFlows((await api.list()).flows)), [run]);
  useEffect(() => { void reload(); }, [reload]);
  const open = (id: string) => void run(async () => {
    const f = await api.get(id); setSel(f); setTrace(null);
    setCanvas(f.live ? await api.canvas(id).catch(() => null) : null);
  });
  const act = (fn: () => Promise<unknown>) => sel && void run(async () => { await fn(); await reload(); open(sel.id); });

  return (
    <main className={s.page}>
      <header className={`${s.head} studio-bar-dark`}><div><FrameMeta /><h1 className={s.title}>Flows</h1><p className={s.muted}>Every change is a version: test, approve, roll out a little, then all the way. Roll back any time.</p></div></header>
      {err && <p className={s.err} role="alert">{err}</p>}
      <section className={s.grid} aria-label="Flows">
        {flows.map((f) => (
          <button key={f.id} className={s.card} aria-current={sel?.id === f.id} onClick={() => open(f.id)}>
            <span className={s.name}>{f.id}</span>
            <span className={s.muted}>{f.live ? `v${f.live} live` : "not live"}{f.candidate ? ` · v${f.candidate} at ${f.rollout}%` : ""}</span>
          </button>
        ))}
        {!flows.length && !busy && <p className={s.muted}>No flows yet. Start from Connect any app.</p>}
      </section>
      {sel && (
        <section className={s.panel} aria-label={`Flow ${sel.id}`}>
          <h2>{sel.id}</h2>
          {canvas && <Canvas c={canvas} />}
          <div className={s.row}>
            <span>Last hour: {Object.entries(sel.monitor.counts).map(([k, v]) => `${v} ${k}`).join(", ") || "no traffic"}</span>
            {sel.monitor.volume ? <span className={s.status} title="Records moved in the last hour, 5-minute steps">Last hour <WithTable label="Records moved, last hour" rows={sel.monitor.volume.map((n, i, all) => [`${(all.length - i) * 5} min ago`, n])}><Sparkline values={sel.monitor.volume} label="Records moved, last hour" ghost="Fills in when records start moving" /></WithTable></span> : null}
            {sel.monitor.error_rate > 0 && <span className={s.status} data-s="warn">Error rate {Math.round(sel.monitor.error_rate * 100)}%</span>}
          </div>
          <table className={s.table}>
            <thead><tr><th>Version</th><th>Status</th><th>Money</th><th /></tr></thead>
            <tbody>
              {sel.versions.map((v) => (
                <tr key={v.n}>
                  <td>v{v.n} <span className={s.muted}>{v.hash}</span></td>
                  <td>{v.status}{sel.candidate === v.n ? ` · ${sel.rollout}%` : ""}</td>
                  <td>{v.money ? <span className={`${s.tag} ${s.money}`}>second approver</span> : "—"}</td>
                  <td className={s.row}>
                    {v.status === "review" && (v.money ? (
                      <span className={s.row}>
                        <input className={s.input} aria-label="Your name (second approver)" placeholder="Your name" maxLength={80} value={approverName} onChange={(e) => setApproverName(e.target.value)} title="Money flows need a second person. If sign-in is off, type your name so Ingenium can tell the two people apart." />
                        <button className={s.btn} disabled={busy} onClick={() => act(() => api.approve(sel.id, v.n, v.hash, approverName.trim() || undefined))}>Approve as second person</button>
                      </span>
                    ) : <button className={s.btn} disabled={busy} onClick={() => act(() => api.approve(sel.id, v.n, v.hash))}>Approve</button>)}
                    {v.status === "approved" && STEPS.map((p) => <button key={p} className={s.btn} disabled={busy} onClick={() => act(async () => { await api.rollout(sel.id, v.n, p); if (p === 100) markSuccess({ title: `${sel.id} is live for everyone`, firstKey: "bridge.firstLive", summary: [`Version ${v.n} now handles 100% of records`, "You can roll back from this board at any time"] }); })}>{p}%</button>)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className={s.row}>
            {busy ? <button className={s.btn} disabled>Roll back</button> : <HoldButton className={s.btn} onConfirm={() => act(() => api.rollback(sel.id))}>Hold to roll back</HoldButton>}
            <a className={s.btn} href={`${getApiBase()}${api.exportUrl(sel.id, "service")}`}>Download service</a>
            <a className={s.btn} href={`${getApiBase()}${api.exportUrl(sel.id, "module")}`}>Download Odoo module</a>
          </div>
          <h3>Follow one record</h3>
          <div className={s.row}>
            <input className={s.input} placeholder="Record id from the app" value={key} onChange={(e) => setKey(e.target.value)} aria-label="Record id" />
            <button className={s.btn} disabled={busy || !key} onClick={() => void run(async () => setTrace((await api.trace(sel.id, key)).events))}>Trace</button>
          </div>
          {trace && trace.length ? <TransitMap events={trace} appName={String((sel.versions.at(-1) as { defn?: { connector?: unknown } } | undefined)?.defn?.connector ?? "App")} /> : null}
          {trace && (trace.length ? <ol className={s.steps}>{trace.map((t, i) => <li key={i}>{new Date(t.at * 1000).toLocaleString()} · {t.step} · {t.status}{t.detail ? ` · ${t.detail}` : ""}</li>)}</ol> : <p className={s.muted}>No events for this record.</p>)}
        </section>
      )}
    </main>
  );
}
