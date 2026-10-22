"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { connectionsApi } from "@/lib/api/connections";
import { suiteApi, upkeepApi, type Localization, type MoneyGuard, type UpgradeReport } from "@/lib/api/suite";
import { viewEngine2cApi, type ApprovalPayload, type Item2c } from "@/lib/api/view-engine-2c";
import { errText, useSuite } from "./SuiteContext";
import { UpgradeForecastPanel } from "./EveryVersion";
import { PageHead, Status } from "./parts";
import styles from "./Suite.module.css";

function SafetyTabs({ active }: { active: "check" | "upgrade" | "money" | "approvals" }) {
  const { connectionId } = useSuite();
  const s = `/connections/${connectionId}/suite/safety`;
  return (
    <nav aria-label="Safety" className={styles.row}>
      <Link href={`${s}/check`} aria-current={active === "check" ? "page" : undefined}>Check a plan</Link>
      <Link href={`${s}/upgrade`} aria-current={active === "upgrade" ? "page" : undefined}>After an upgrade</Link>
      <Link href={`${s}/money`} aria-current={active === "money" ? "page" : undefined}>Money guard</Link>
      <Link href={`${s}/approvals`} aria-current={active === "approvals" ? "page" : undefined}>Approvals</Link>
    </nav>
  );
}

/** Safety check (spec 7.2): the same read-only Check every run needs, with its receipt. */
export function SafetyCheck() {
  const { connectionId } = useSuite();
  const [plans, setPlans] = useState<{ id: string; name: string; steps: number }[]>([]);
  useEffect(() => { suiteApi.plans(connectionId).then((r) => setPlans(r.plans), () => undefined); }, [connectionId]);
  return (
    <>
      <PageHead title="Safety" purpose="Nothing writes without a check. A check reads only, gives every step a verdict, and its receipt lasts one hour for that exact plan." />
      <SafetyTabs active="check" />
      <section className={styles.section}>
        <h2>Plans to check</h2>
        {plans.length ? <ul className={styles.list}>{plans.map((p) => <li key={p.id}><Link href={`/connections/${connectionId}/suite/setup?plan=${p.id}&view=board`}>{p.name}</Link> <span className={styles.muted}>{p.steps} steps</span></li>)}</ul>
          : <p className={styles.muted}>No plans yet. <Link href={`/connections/${connectionId}/suite/setup`}>Start one in Set up</Link>.</p>}
      </section>
    </>
  );
}

export function SafetyUpgrade() {
  const { connectionId } = useSuite();
  const [conns, setConns] = useState<{ id: string; name: string }[]>([]);
  const [target, setTarget] = useState("");
  const [rep, setRep] = useState<UpgradeReport | null>(null);
  const [fix, setFix] = useState<Record<number, { passes: boolean; missing: string[]; note?: string }>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => { connectionsApi.listConnections().then((c) => setConns(c.filter((x) => x.id !== connectionId).map((x) => ({ id: x.id, name: x.name }))), () => undefined); }, [connectionId]);
  useEffect(() => { setRep(null); upkeepApi.upgrade(connectionId, target || undefined).then(setRep, (e: unknown) => setError(errText(e))); }, [connectionId, target]);
  async function checkFix(viewId: number) {
    setBusy(String(viewId)); setError(null);
    try { const r = await upkeepApi.checkFix(connectionId, target, viewId); setFix((f) => ({ ...f, [viewId]: r })); } catch (e) { setError(errText(e)); } finally { setBusy(null); }
  }
  return (
    <>
      <PageHead title="After an upgrade" purpose="Which of your tracked changes still fit, checked against the facts of the version they are going to." />
      <SafetyTabs active="upgrade" />
      <UpgradeForecastPanel />
      <label className={styles.row}>Compare with the upgraded copy
        <select value={target} onChange={(e) => setTarget(e.target.value)} data-testid="upgrade-target">
          <option value="">This database&apos;s own version</option>{conns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </label>
      {error ? <Status tone="danger">{error}</Status> : null}
      {!rep ? <Status tone="busy">Reading…</Status> : (
        <>
          <ul className={styles.list} aria-label="Timeline">{rep.timeline.map((t) => <li key={t.what}>{t.what}: {t.value}</li>)}</ul>
          <p data-testid="upgrade-summary">Odoo {rep.from_version} to {rep.target_version}: {rep.changes.length} tracked changes, {rep.needs_fix} need a fix.</p>
          <table className={styles.table} data-testid="upgrade-matrix">
            <thead><tr><th scope="col">Change</th><th scope="col">Screen</th><th scope="col">On {rep.target_version}</th><th scope="col"><span className={styles.muted}>Fix</span></th></tr></thead>
            <tbody>
              {rep.changes.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>{c.model} {c.type}</td>
                  <td>{c.flags.length ? c.flags.map((f) => <Status key={f.key} tone="warning">{f.text}</Status>) : <Status tone="success">Still fits</Status>}</td>
                  <td>
                    {c.flags.length && target ? <Button size="sm" variant="secondary" loading={busy === String(c.id)} onClick={() => void checkFix(c.id)}>Check the fix</Button> : null}
                    {fix[c.id] ? <Status tone={fix[c.id].passes ? "success" : "warning"}>{fix[c.id].passes ? "The fix passes Check on the upgraded copy. Nothing was written." : fix[c.id].note ?? `Not found there: ${fix[c.id].missing.join(", ")}`}</Status> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}

/** Suite approvals live in the builders' approvals list; someone other than the requester decides. */
export function SafetyApprovals() {
  const { connectionId } = useSuite();
  const [items, setItems] = useState<Item2c<ApprovalPayload & { action?: string }>[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const load = () => { viewEngine2cApi.approvals(connectionId, "suite").then((r) => setItems(r.approvals as Item2c<ApprovalPayload & { action?: string }>[]), (e: unknown) => setError(errText(e))); };
  useEffect(load, [connectionId]);
  async function decide(id: string, approve: boolean) {
    setBusy(id); setError(null);
    try { await viewEngine2cApi.approvalDecide(connectionId, id, approve); load(); } catch (e) { setError(errText(e)); } finally { setBusy(null); }
  }
  return (
    <>
      <PageHead title="Approvals" purpose="Setup plans and batch changes that need a second person. The same list the View Designer uses." />
      <SafetyTabs active="approvals" />
      {error ? <Status tone="danger">{error}</Status> : null}
      {!items ? <Status tone="busy">Reading…</Status> : !items.length ? <p className={styles.muted}>Nothing waiting.</p> : (
        <ul className={styles.list} data-testid="suite-approvals">
          {items.map((it) => (
            <li key={it.id} className={styles.card}>
              <p className={styles.flush}><strong>{it.name}</strong> <span className={styles.muted}>asked by {it.payload.requested_by}{it.payload.identity_verified ? "" : " (sign-in not verified)"}</span></p>
              <ul className={styles.list}>{(it.payload.summary ?? []).slice(1).map((x, i) => <li key={i} className={styles.muted}>{x}</li>)}</ul>
              {it.payload.status === "pending" ? (
                <div className={styles.row}>
                  <Button size="sm" variant="primary" loading={busy === it.id} onClick={() => void decide(it.id, true)}>Approve</Button>
                  <Button size="sm" variant="secondary" disabled={busy === it.id} onClick={() => void decide(it.id, false)}>Decline</Button>
                </div>
              ) : <Status tone={it.payload.status === "approved" ? "success" : "info"}>{it.payload.status === "approved" ? `Approved by ${it.payload.decided_by}` : it.payload.status}</Status>}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function LocalizationCard() {
  const { connectionId } = useSuite();
  const [loc, setLoc] = useState<Localization | null>(null);
  useEffect(() => { upkeepApi.localization(connectionId).then(setLoc, () => undefined); }, [connectionId]);
  if (!loc) return null;
  return (
    <section className={styles.card} aria-label="Localization" data-testid="suite-localization">
      <p className={styles.flush}><strong>{loc.companies.map((c) => `${c.name} (${c.country ?? "no country"}, ${c.currency ?? ""})`).join(" · ")}</strong></p>
      <p className={styles.mutedLine}>Country packages: {loc.country_packages.length ? loc.country_packages.join(", ") : "none"}</p>
      <p className={styles.mutedLine}>{loc.rule}</p>
      <ul className={styles.list}>{Object.entries(loc.routes).map(([k, v]) => <li key={k}>{k}: {v}</li>)}</ul>
    </section>
  );
}

export function SafetyMoney() {
  const { connectionId } = useSuite();
  const [data, setData] = useState<MoneyGuard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [threshold, setThreshold] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { suiteApi.money(connectionId).then((d) => { setData(d); setThreshold(String(d.policy.approval_threshold)); }, (e: unknown) => setError(errText(e))); }, [connectionId]);
  async function save(body: { approval_threshold?: number; cloud_ai?: boolean }) {
    setBusy(true);
    try { const pol = await suiteApi.setPolicy(connectionId, body); setData((d) => (d ? { ...d, policy: pol } : d)); } catch (e) { setError(errText(e)); } finally { setBusy(false); }
  }
  return (
    <>
      <PageHead title="Money guard" purpose="Accounting stays safe: what the suite never does, and what it does only before the first posted entry." />
      <SafetyTabs active="money" />
      {error ? <Status tone="danger">{error}</Status> : null}
      {!data ? <Status tone="busy">Reading…</Status> : (
        <>
          <LocalizationCard />
          <p data-testid="suite-money-facts">{data.facts.posted_entries} posted entries · {data.facts.done_moves} done stock moves</p>
          <ul className={styles.list} data-testid="suite-money-rules">
            {data.rules.map((r) => (
              <li key={r.key}><Status tone={r.allowed_now === false ? "warning" : "info"}>{r.text}{r.allowed_now === undefined ? "" : r.allowed_now ? " Open on this database." : " Closed on this database."}</Status></li>
            ))}
          </ul>
          <section className={styles.section} aria-labelledby="pol-h">
            <h2 id="pol-h">This database&apos;s rules</h2>
            <form className={styles.row} onSubmit={(e) => { e.preventDefault(); const n = parseInt(threshold, 10); if (n > 0) void save({ approval_threshold: n }); }}>
              <label htmlFor="suite-threshold">Ask for approval above</label>
              <input id="suite-threshold" inputMode="numeric" value={threshold} onChange={(e) => setThreshold(e.target.value)} size={6} />
              <span>hard-to-undo records</span>
              <Button type="submit" size="sm" loading={busy}>Save</Button>
            </form>
            <label className={styles.row}>
              <input type="checkbox" checked={data.policy.cloud_ai} disabled={busy} onChange={(e) => void save({ cloud_ai: e.target.checked })} />
              Allow cloud AI for this client (local AI is the default){data.policy.cloud_ai_consent_by ? `. Consent recorded by ${data.policy.cloud_ai_consent_by}.` : ""}
            </label>
          </section>
        </>
      )}
    </>
  );
}
