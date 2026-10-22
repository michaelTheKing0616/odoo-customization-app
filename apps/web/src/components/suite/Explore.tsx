"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { suiteApi, type Capability, type Inspector } from "@/lib/api/suite";
import { errText, useSuite } from "./SuiteContext";
import { PageHead, Status } from "./parts";
import styles from "./Suite.module.css";

function ExploreTabs({ active }: { active: "capabilities" | "models" }) {
  const { connectionId } = useSuite();
  const s = `/connections/${connectionId}/suite/explore`;
  return (
    <nav aria-label="Explore" className={styles.row}>
      <Link href={`${s}/capabilities`} aria-current={active === "capabilities" ? "page" : undefined}>What this database can do</Link>
      <Link href={`${s}/models/res.partner`} aria-current={active === "models" ? "page" : undefined}>Inspect a model</Link>
    </nav>
  );
}

const AVAIL: Record<string, { tone: "success" | "warning" | "danger"; word: string }> = {
  yes: { tone: "success", word: "Available" }, partial: { tone: "warning", word: "Partly" }, no: { tone: "danger", word: "Not here" },
};

export function ExploreCapabilities() {
  const { connectionId } = useSuite();
  const [data, setData] = useState<{ version: string; capabilities: Capability[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { suiteApi.capabilities(connectionId).then(setData, (e: unknown) => setError(errText(e))); }, [connectionId]);
  return (
    <>
      <PageHead title="Explore" purpose="What this database can do, decided from its version, edition, hosting and apps." />
      <ExploreTabs active="capabilities" />
      {error ? <Status tone="danger">{error}</Status> : !data ? <Status tone="busy">Reading…</Status> : (
        <table className={styles.table} data-testid="suite-capabilities">
          <thead><tr><th scope="col">Capability</th><th scope="col">Here</th><th scope="col">Why</th><th scope="col">What you can do</th></tr></thead>
          <tbody>
            {data.capabilities.map((c) => {
              const a = AVAIL[c.available] ?? { tone: "warning" as const, word: c.available };
              return (
                <tr key={c.key} data-key={c.key} data-available={c.available}>
                  <td>{c.label}</td><td><Status tone={a.tone}>{a.word}</Status></td><td>{c.reason}</td><td>{c.options.join(" ")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </>
  );
}

export function ExploreModel({ model }: { model: string }) {
  const { connectionId } = useSuite();
  const router = useRouter();
  const [data, setData] = useState<Inspector | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState(model);
  useEffect(() => {
    setData(null); setError(null);
    suiteApi.inspector(connectionId, model).then(setData, (e: unknown) => setError(errText(e)));
  }, [connectionId, model]);
  const indent = (d: number) => [styles.indent1, styles.indent1, styles.indent2, styles.indent3][Math.min(d, 3)];
  return (
    <>
      <PageHead title="Inspect a model" purpose="Fields with how often they are filled, links, the screen layers in Odoo's order, and who can see it." />
      <ExploreTabs active="models" />
      <form className={styles.row} onSubmit={(e) => { e.preventDefault(); if (q.trim()) router.push(`/connections/${connectionId}/suite/explore/models/${encodeURIComponent(q.trim())}`); }}>
        <label htmlFor="suite-model">Model</label>
        <input id="suite-model" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Contacts, Quotations, Leads..." />
        <Button type="submit" size="sm">Inspect</Button>
      </form>
      {error ? <Status tone="danger">{error}</Status> : !data ? <Status tone="busy">Reading {model}…</Status> : (
        <div data-testid="suite-inspector">
          <p>{data.records} records · {data.fields.length} fields · {data.links.length} linked models</p>
          <section className={styles.section} aria-labelledby="layers-h">
            <h2 id="layers-h">Form screen layers, in Odoo&apos;s order</h2>
            <ol className={styles.list} data-testid="suite-view-stack">
              {data.views.form.map((v) => (
                <li key={v.id} className={indent(v.depth)} data-depth={v.depth}>{v.name} <span className={styles.muted}>{v.mode === "primary" ? "base screen" : "change"} · priority {v.priority}{v.key ? ` · ${v.key}` : ""}</span></li>
              ))}
            </ol>
          </section>
          <section className={styles.section} aria-labelledby="fields-h">
            <h2 id="fields-h">Fields</h2>
            <table className={styles.table}>
              <thead><tr><th scope="col">Field</th><th scope="col">Type</th><th scope="col">Filled</th><th scope="col">Required</th></tr></thead>
              <tbody>
                {data.fields.map((f) => (
                  <tr key={f.name}>
                    <td>{f.label} <span className={styles.muted}>{f.name}</span></td>
                    <td>{f.type}{f.relation ? <> to <Link href={`/connections/${connectionId}/suite/explore/models/${f.relation}`}>{f.relation}</Link></> : null}</td>
                    <td>{f.filled === null ? <span className={styles.muted}>not counted</span> : `${f.filled} of ${data.records}`}</td>
                    <td>{f.required ? "Yes" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <section className={styles.section} aria-labelledby="access-h">
            <h2 id="access-h">Access</h2>
            <ul className={styles.list}>{data.access.map((a, i) => <li key={i}>{String(a.group)}: {["perm_read", "perm_write", "perm_create", "perm_unlink"].filter((k) => a[k]).map((k) => k.replace("perm_", "")).join(", ") || String(a.name)}</li>)}</ul>
          </section>
        </div>
      )}
    </>
  );
}
