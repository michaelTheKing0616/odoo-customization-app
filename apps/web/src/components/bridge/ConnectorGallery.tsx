"use client";

/* Bridge B1: connector gallery (1), guided auth into the vault (3), health check on connect (4).
   Secret values are write-only from here: the API returns field names, never values. */
import { useCallback, useEffect, useMemo, useState } from "react";
import { bridgeGalleryApi as api, type BGConnector, type BGDetail, type BGHealth } from "@/lib/api/bridge-gallery";
import { connectionsApi } from "@/lib/api/connections";
import type { Connection } from "@/lib/api/types-schema";
import s from "./Gallery.module.css";
import { FrameMeta } from "@/components/frame/FrameMeta";

const msg = (e: unknown) => (e instanceof Error ? e.message : String(e));
const label = (k: string) => k.replace(/_/g, " ");
const EXTRA: Record<string, string[]> = { shopify: ["shop"], woocommerce: ["base_url"], quickbooks: ["realm"] };

export function ConnectorGallery() {
  const [items, setItems] = useState<BGConnector[]>([]);
  const [cats, setCats] = useState<string[]>([]);
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<BGDetail | null>(null);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [conns, setConns] = useState<Connection[]>([]);
  const [odooId, setOdooId] = useState("");
  const [need, setNeed] = useState<string[]>([]);
  const [health, setHealth] = useState<BGHealth | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const run = useCallback(async <T,>(fn: () => Promise<T>) => {
    setBusy(true); setErr("");
    try { return await fn(); } catch (e) { setErr(msg(e)); return undefined; } finally { setBusy(false); }
  }, []);

  useEffect(() => {
    void run(async () => { const r = await api.list(); setItems(r.connectors); setCats(r.categories); });
    connectionsApi.listConnections().then(setConns).catch(() => setConns([]));
  }, [run]);

  const shown = useMemo(() => items.filter((c) => (!cat || c.category === cat)
    && (!q || `${c.name} ${c.key} ${c.entities.join(" ")}`.toLowerCase().includes(q.toLowerCase()))), [items, cat, q]);

  const open = (key: string) => void run(async () => {
    const d = await api.get(key); setSel(d); setVals({}); setHealth(null); setNeed(d.entities);
  });
  const fields = sel ? [...(EXTRA[sel.key] ?? []), ...sel.auth_plan.vault_fields] : [];
  const save = () => sel && void run(async () => {
    const values = Object.fromEntries(Object.entries(vals).filter(([, v]) => v.trim()));
    await api.saveSecrets(sel.key, values); setVals({}); setSel(await api.get(sel.key));
  });
  const check = () => sel && void run(async () => setHealth(await api.health(sel.key, { needed_entities: need, odoo_connection_id: odooId || null })));
  const forget = () => sel && void run(async () => { await api.forget(sel.key); setSel(await api.get(sel.key)); setHealth(null); });

  return (
    <main className={s.page}>
      <header className={`${s.head} studio-bar-dark`}>
        <div>
          <FrameMeta />
          <h1 className={s.title}>Connect an app</h1>
          <p className={s.muted}>Pick an app, sign in, and we check the connection before any data moves.</p>
        </div>
        <span className={s.spacer} />
        <input className={s.input} placeholder="Search apps or data (e.g. invoices)" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search connectors" />
      </header>
      <div className={s.chips} role="group" aria-label="Category">
        <button className={s.chip} aria-pressed={!cat} onClick={() => setCat("")}>All</button>
        {cats.map((c) => <button key={c} className={s.chip} aria-pressed={cat === c} onClick={() => setCat(c)}>{label(c)}</button>)}
      </div>
      {err && <p className={s.err} role="alert">{err}</p>}
      <section className={s.grid} aria-label="Connectors">
        {shown.map((c) => (
          <button key={c.key} className={s.card} aria-current={sel?.key === c.key} onClick={() => open(c.key)}>
            <span className={s.name}>{c.name}</span>
            <span className={s.muted}>{label(c.category)}{c.status === "template" ? " · template" : ""}</span>
            <span className={s.tags}>
              {c.auth.map((a) => <span key={a} className={s.tag}>{label(a)}</span>)}
              {c.money && <span className={`${s.tag} ${s.money}`}>money guard</span>}
            </span>
          </button>
        ))}
        {!shown.length && !busy && <p className={s.muted}>No app matches. Try another word.</p>}
      </section>

      {sel && (
        <section className={s.panel} aria-label={`Connect ${sel.name}`}>
          <h2>Connect {sel.name}</h2>
          <ol className={s.steps}>{sel.auth_plan.steps.map((st) => <li key={st.kind}>{st.step}{st.refresh ? " (we refresh the sign-in for you)" : ""}</li>)}</ol>
          {sel.money && <p className={s.status} data-s="warn">This app moves money. Every flow gets the money guard and a daily reconciliation check.</p>}
          <div className={s.row}>
            {fields.map((f) => (
              <label key={f} className={s.field}>
                <span>{label(f)}{sel.stored.some((x) => x.name === f) ? " · saved" : ""}</span>
                <input className={s.input} type={EXTRA[sel.key]?.includes(f) ? "text" : "password"} autoComplete="off"
                  value={vals[f] ?? ""} onChange={(e) => setVals({ ...vals, [f]: e.target.value })} />
              </label>
            ))}
          </div>
          <div className={s.row}>
            <button className={`${s.btn} ${s.primary}`} disabled={busy || !Object.values(vals).some((v) => v.trim())} onClick={save}>Save to vault</button>
            {sel.stored.length > 0 && <button className={s.btn} disabled={busy} onClick={forget}>Forget saved keys</button>}
          </div>
          <h3>Check the connection</h3>
          <div className={s.row}>
            <label className={s.field}><span>Odoo database</span>
              <select className={s.select} value={odooId} onChange={(e) => setOdooId(e.target.value)}>
                <option value="">Skip Odoo check</option>
                {conns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <div className={s.chips} role="group" aria-label="Data to sync">
              {sel.entities.map((e) => (
                <button key={e} className={s.chip} aria-pressed={need.includes(e)}
                  onClick={() => setNeed(need.includes(e) ? need.filter((x) => x !== e) : [...need, e])}>{label(e)}</button>
              ))}
            </div>
          </div>
          <div className={s.row}>
            <button className={`${s.btn} ${s.primary}`} disabled={busy} onClick={check}>{busy ? "Checking…" : "Run health check"}</button>
            {!sel.live_check && <span className={s.muted}>Live sign-in check comes with this app&apos;s setup.</span>}
          </div>
          {health && (
            <div className={s.status} data-s={health.status} role="status">
              <strong>{health.status === "ok" ? "Ready" : health.status === "warn" ? "Works, with notes" : "Not ready"}</strong>
              {health.issues.map((i) => <div key={i}>{i}</div>)}
              {health.warnings.map((w) => <div key={w}>{w}</div>)}
              {health.rate_limit && <div>Rate limit: {health.rate_limit.remaining} of {health.rate_limit.limit} left</div>}
              {health.odoo && <div>Odoo: {health.odoo.ok ? `ok (version ${health.odoo.version}, ${health.odoo.partners} contacts)` : health.odoo.error}</div>}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
