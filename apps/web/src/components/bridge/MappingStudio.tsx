"use client";

/* Bridge B2 + B3: read an API description or sample, then map its fields onto an Odoo model.
   Matches and checks come from the server; every edit is re-checked there before it counts. */
import { ConfidenceMark } from "@/components/ui/craft";
import { useCallback, useEffect, useState } from "react";
import { bridgeBuildApi as api, bridgeTestApi as tapi, type BGMapOut, type BGMapRow, type BGSandbox, type BGSpec, type BGTests } from "@/lib/api/bridge-gallery";
import { connectionsApi } from "@/lib/api/connections";
import type { Connection } from "@/lib/api/types-schema";
import s from "./Gallery.module.css";
import { FrameMeta } from "@/components/frame/FrameMeta";

const msg = (e: unknown) => (e instanceof Error ? e.message : String(e));
const pct = (n: number) => `${Math.round(n * 100)}%`;

export function MappingStudio() {
  const [text, setText] = useState("");
  const [spec, setSpec] = useState<BGSpec | null>(null);
  const [entity, setEntity] = useState("");
  const [sample, setSample] = useState("");
  const [conns, setConns] = useState<Connection[]>([]);
  const [conn, setConn] = useState("");
  const [model, setModel] = useState("res.partner");
  const [out, setOut] = useState<BGMapOut | null>(null);
  const [rows, setRows] = useState<BGMapRow[]>([]);
  const [tests, setTests] = useState<BGTests | null>(null);
  const [sbx, setSbx] = useState<BGSandbox | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => { connectionsApi.listConnections().then(setConns).catch(() => setConns([])); }, []);
  const run = useCallback(async <T,>(fn: () => Promise<T>) => {
    setBusy(true); setErr("");
    try { return await fn(); } catch (e) { setErr(msg(e)); return undefined; } finally { setBusy(false); }
  }, []);

  const read = () => void run(async () => {
    const d = await api.importSpec(text); setSpec(d); setEntity(Object.keys(d.entities)[0] ?? ""); setOut(null);
  });
  const samples = (): Record<string, unknown>[] => {
    if (!sample.trim()) return [];
    const v: unknown = JSON.parse(sample);
    return (Array.isArray(v) ? v : [v]) as Record<string, unknown>[];
  };
  const check = (mapping?: BGMapRow[]) => spec && entity && conn && void run(async () => {
    const d = await api.mapping({ odoo_connection_id: conn, model, remote_fields: spec.entities[entity].fields, samples: samples(), mapping });
    setOut(d); setRows(d.mapping);
  });
  const body = () => ({ odoo_connection_id: conn, model, remote_fields: spec!.entities[entity].fields, mapping: rows, samples: samples() });
  const runTests = () => spec && void run(async () => setTests(await tapi.contractTests(body())));
  const runSandbox = () => spec && void run(async () => setSbx(await tapi.sandbox(body())));
  const edit = (i: number, patch: Partial<BGMapRow>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch, confidence: patch.odoo !== undefined ? 1 : r.confidence } : r)));

  return (
    <main className={s.page}>
      <header className={`${s.head} studio-bar-dark`}>
        <div>
          <FrameMeta />
          <h1 className={s.title}>Connect any app</h1>
          <p className={s.muted}>Paste API docs (OpenAPI, Swagger, Postman) or one sample record. We read it, then you match its fields to Odoo.</p>
        </div>
      </header>
      {err && <p className={s.err} role="alert">{err}</p>}
      <section className={s.panel} aria-label="Read the app">
        <h2>1. Read the app</h2>
        <textarea className={s.input} rows={8} value={text} onChange={(e) => setText(e.target.value)} aria-label="API description or sample" placeholder='{"openapi": "3.0.0", ...} or {"orders": [{"id": 1, "total": 2.5}]}' />
        <div className={s.row}><button className={`${s.btn} ${s.primary}`} disabled={busy || !text.trim()} onClick={read}>Read it</button></div>
        {spec && (
          <div className={s.row}>
            <span><strong>{spec.name}</strong> · {spec.base_url || "no base URL"} · sign-in: {spec.auth.join(", ")}</span>
            {spec.checks.map((c) => <span key={c} className={s.status} data-s="warn">{c}</span>)}
          </div>
        )}
      </section>
      {spec && (
        <section className={s.panel} aria-label="Match fields">
          <h2>2. Match fields to Odoo</h2>
          <div className={s.row}>
            <label className={s.field}><span>Data from the app</span>
              <select className={s.select} value={entity} onChange={(e) => setEntity(e.target.value)}>
                {Object.keys(spec.entities).map((k) => <option key={k} value={k}>{k}</option>)}
              </select></label>
            <label className={s.field}><span>Odoo database</span>
              <select className={s.select} value={conn} onChange={(e) => setConn(e.target.value)}>
                <option value="">Choose…</option>{conns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select></label>
            <label className={s.field}><span>Odoo model</span><input className={s.input} value={model} onChange={(e) => setModel(e.target.value)} /></label>
          </div>
          <label className={s.field}><span>Sample records for the preview (JSON, optional)</span>
            <textarea className={s.input} rows={3} value={sample} onChange={(e) => setSample(e.target.value)} /></label>
          <div className={s.row}>
            <button className={`${s.btn} ${s.primary}`} disabled={busy || !conn || !entity} onClick={() => check()}>Suggest matches</button>
            {out && <button className={s.btn} disabled={busy} onClick={() => check(rows)}>Check my changes</button>}
          </div>
          {out && (
            <>
              <table className={s.table}>
                <thead><tr><th>App field</th><th>Odoo field</th><th>Change on the way</th><th>Match</th></tr></thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={r.remote}>
                      <td>{r.remote} <span className={s.muted}>({spec.entities[entity].fields[r.remote]})</span></td>
                      <td><select className={s.select} value={r.odoo ?? ""} onChange={(e) => edit(i, { odoo: e.target.value || null })}>
                        <option value="">Don&apos;t sync</option>
                        {Object.entries(out.odoo_fields).map(([k, f]) => <option key={k} value={k}>{f.string} ({k}){f.required ? " *" : ""}</option>)}
                      </select></td>
                      <td><select className={s.select} value={r.transform} onChange={(e) => edit(i, { transform: e.target.value })}>
                        {out.transforms.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
                      </select></td>
                      <td>{r.odoo ? <><ConfidenceMark level={r.confidence >= 0.8 ? 3 : r.confidence >= 0.5 ? 2 : 1} reason={`Match score ${pct(r.confidence)}`} /> {pct(r.confidence)}</> : "—"}{r.money ? <span className={`${s.tag} ${s.money}`}> money</span> : null}{r.needs_review ? " · check" : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {out.errors.length ? out.errors.map((e) => <p key={e} className={s.status} data-s="fail">{e}</p>) : <p className={s.status} data-s="ok">All matches pass the checks.</p>}
              {out.preview.length > 0 && (
                <div><h3>Preview on your sample</h3>
                  {out.preview.map((p, i) => <pre key={i} className={s.muted}>{JSON.stringify(p.values)}{p.problems.length ? `  ⚠ ${p.problems.join(", ")}` : ""}</pre>)}
                </div>
              )}
            </>
          )}
        </section>
      )}
      {out && (
        <section className={s.panel} aria-label="Test before live">
          <h2>3. Test before it goes live</h2>
          <p className={s.muted}>Tests run your samples through the matches. The sandbox looks up Odoo but writes nothing.</p>
          <div className={s.row}>
            <button className={s.btn} disabled={busy} onClick={runTests}>Run contract tests</button>
            <button className={`${s.btn} ${s.primary}`} disabled={busy} onClick={runSandbox}>Sandbox run</button>
          </div>
          {tests && (
            <div className={s.status} data-s={tests.ok ? "ok" : "fail"} role="status">
              <strong>{tests.ok ? "All tests pass" : "Tests failed"}</strong>
              {tests.mapping_errors.map((e) => <div key={e}>{e}</div>)}
              {tests.cases.filter((c) => !c.ok).map((c) => <div key={c.sample}>Sample {c.sample + 1}: {c.problems.join(", ")}</div>)}
            </div>
          )}
          {sbx && (
            <div className={s.status} data-s={sbx.ready_for_live ? "ok" : "warn"} role="status">
              <strong>Sandbox: {sbx.counts.create} new, {sbx.counts.link} matched, {sbx.counts.review} to review · nothing written</strong>
              {sbx.plan.filter((p) => p.would === "review").map((p, i) => <div key={i}>Check: {JSON.stringify(p.values)} ({p.why})</div>)}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
