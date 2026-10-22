"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { connectionsApi } from "@/lib/api/connections";
import { suiteApi, upkeepApi, type EveryVersionReport, type UpgradeForecast } from "@/lib/api/suite";
import { errText, useSuite } from "./SuiteContext";
import { Status } from "./parts";
import styles from "./Suite.module.css";

/** Stage 4: the same plan checked (reads only) on other saved databases, e.g. test copies on Odoo 17-20. */
export function CheckEveryVersion({ planId }: { planId: string }) {
  const { connectionId } = useSuite();
  const [conns, setConns] = useState<{ id: string; name: string }[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [rep, setRep] = useState<EveryVersionReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    connectionsApi.listConnections().then((c) => setConns(c.filter((x) => x.id !== connectionId).map((x) => ({ id: x.id, name: x.name }))), () => undefined);
  }, [connectionId]);
  const name = (id: string) => (id === connectionId ? "This database" : conns.find((c) => c.id === id)?.name ?? id);
  async function run() {
    setBusy(true); setError(null);
    try { setRep(await suiteApi.checkEveryVersion(connectionId, planId, picked)); } catch (e) { setError(errText(e)); } finally { setBusy(false); }
  }
  if (!conns.length) return null;
  return (
    <section className={styles.section} aria-labelledby="every-version-h" data-testid="every-version">
      <h2 id="every-version-h">Check on other databases</h2>
      <p className={styles.muted}>Reads only. Each database still needs its own Check before it can run.</p>
      <fieldset className={styles.row}>
        <legend className={styles.muted}>Databases</legend>
        {conns.map((c) => (
          <label key={c.id}>
            <input type="checkbox" checked={picked.includes(c.id)} onChange={(e) => setPicked((p) => (e.target.checked ? [...p, c.id] : p.filter((x) => x !== c.id)))} /> {c.name}
          </label>
        ))}
      </fieldset>
      <Button size="sm" variant="secondary" loading={busy} disabled={!picked.length} onClick={() => void run()} data-testid="every-version-run">Check on {picked.length || "these"} database{picked.length === 1 ? "" : "s"}</Button>
      {error ? <Status tone="danger">{error}</Status> : null}
      {rep ? (
        <>
          <Status tone={rep.same_everywhere ? "success" : "warning"}>{rep.same_everywhere ? "Same result everywhere." : "The result differs between databases. See below."}</Status>
          <table className={styles.table}>
            <thead><tr><th scope="col">Database</th><th scope="col">Odoo</th><th scope="col">Result</th><th scope="col">What to fix</th></tr></thead>
            <tbody>
              {rep.results.map((r) => (
                <tr key={r.connection_id}>
                  <td>{name(r.connection_id)}</td>
                  <td className={styles.num}>{r.version ?? "–"}</td>
                  <td>{r.error ? <Status tone="danger">{r.error}</Status> : <Status tone={r.can_apply ? "success" : "warning"}>{r.counts?.ready ?? 0} ready, {(r.counts?.blocked ?? 0) + (r.counts?.needs_input ?? 0)} to fix</Status>}</td>
                  <td>{r.problems?.length ? <ul className={styles.list}>{r.problems.map((p) => <li key={p.step}>{p.step}: {p.message}</li>)}</ul> : <span className={styles.muted}>Nothing</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </section>
  );
}

/** Stage 4 "Before you upgrade": what each newer version would need, from what we track. Reads only. */
export function UpgradeForecastPanel() {
  const { connectionId } = useSuite();
  const [f, setF] = useState<UpgradeForecast | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setF(null); upkeepApi.forecast(connectionId).then(setF, (e: unknown) => setError(errText(e))); }, [connectionId]);
  return (
    <section className={styles.section} aria-labelledby="forecast-h" data-testid="upgrade-forecast">
      <h2 id="forecast-h">Before you upgrade</h2>
      {error ? <Status tone="danger">{error}</Status> : !f ? <Status tone="busy">Reading…</Status> : (
        <>
          <p>{f.summary}</p>
          {f.steps.length ? (
            <table className={styles.table}>
              <thead><tr><th scope="col">To Odoo</th><th scope="col">Screens to fix</th><th scope="col">We can rewrite</th><th scope="col">Data that moves</th></tr></thead>
              <tbody>
                {f.steps.map((s) => (
                  <tr key={s.version}>
                    <th scope="row">{s.version}</th>
                    <td className={styles.num}>{s.screens_to_fix}</td>
                    <td className={styles.num}>{s.auto_fixable}</td>
                    <td>{s.data_moves.length ? <ul className={styles.list}>{s.data_moves.map((m) => <li key={m}>{m}</li>)}</ul> : <span className={styles.muted}>None</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </>
      )}
    </section>
  );
}
