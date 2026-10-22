"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { insightsApi, type InsightCard } from "@/lib/api/suite";
import { errText, useSuite } from "./SuiteContext";
import { PageHead, Status } from "./parts";
import styles from "./Suite.module.css";

/** What each insight asks for before it can look. Everything here reads only. */
const INPUTS: Record<string, { name: string; label: string; placeholder?: string; required?: boolean }[]> = {
  "data-quality": [{ name: "model", label: "Record type (code)", placeholder: "res.partner" }],
  "archive-check": [{ name: "model", label: "Record type (code)", placeholder: "res.partner", required: true }, { name: "ids", label: "Record numbers, comma separated", required: true }],
  "role-xray": [{ name: "user_id", label: "User number", required: true }],
  "access-hygiene": [{ name: "days", label: "Idle for at least (days)", placeholder: "90" }],
  numbering: [{ name: "model", label: "Document type (code)", placeholder: "sale.order" }],
  "unused-apps": [{ name: "days", label: "No new records for (days)", placeholder: "90" }],
  storage: [{ name: "limit_mb", label: "Tell me when files reach (MB)" }],
  "import-aftercare": [{ name: "model", label: "Record type (code)", placeholder: "res.partner" }, { name: "days", label: "Imported in the last (days)", placeholder: "14" }],
  timeline: [{ name: "model", label: "Record type (code)", required: true }, { name: "id", label: "Record number", required: true }],
  compare: [{ name: "other", label: "Other saved database (its Ingenium id)", required: true }],
};

const WORDS: Record<string, string> = { only_here: "Only on this database", only_there: "Only on the other one", on_off_differs: "On here, off there (or the reverse)" };
const human = (k: string) => WORDS[k] ?? (k.charAt(0).toUpperCase() + k.slice(1)).replace(/_/g, " ");
const PROSE = new Set(["note", "next", "summary", "hint", "fix", "error"]);
const HIDDEN = new Set(["code", "id", "idea"]);

function Cell({ v }: { v: unknown }) {
  if (v === null || v === undefined || v === "") return <span className={styles.muted}>–</span>;
  if (typeof v === "boolean") return <>{v ? "Yes" : "No"}</>;
  if (Array.isArray(v)) return v.length ? <>{v.map((x) => (typeof x === "object" ? JSON.stringify(x) : String(x))).join(", ")}</> : <span className={styles.muted}>None</span>;
  if (typeof v === "object") return <>{Object.entries(v as Record<string, unknown>).map(([k, x]) => `${human(k)}: ${String(x)}`).join(" · ")}</>;
  return <>{String(v)}</>;
}

/** Arrays of rows become tables, short values a summary list, notes plain sentences. No raw JSON. */
export function InsightResult({ data }: { data: Record<string, unknown> }) {
  const prose = Object.entries(data).filter(([k, v]) => PROSE.has(k) && typeof v === "string");
  const facts = Object.entries(data).filter(([k, v]) => !PROSE.has(k) && !HIDDEN.has(k) && (typeof v !== "object" || v === null));
  const tables = Object.entries(data).filter(([, v]) => Array.isArray(v) && (v as unknown[]).every((x) => x && typeof x === "object"));
  const lists = Object.entries(data).filter(([, v]) => Array.isArray(v) && (v as unknown[]).some((x) => typeof x !== "object"));
  const groups = Object.entries(data).filter(([, v]) => v && typeof v === "object" && !Array.isArray(v));
  return (
    <div className={styles.section} data-testid="insight-result">
      {prose.map(([k, v]) => <Status key={k} tone={k === "error" ? "danger" : "info"}>{v as string}</Status>)}
      {facts.length ? <dl className={styles.row}>{facts.map(([k, v]) => <div key={k}><dt className={styles.muted}>{human(k)}</dt><dd className={styles.num}><Cell v={v} /></dd></div>)}</dl> : null}
      {tables.map(([k, rows]) => {
        const list = rows as Record<string, unknown>[];
        const cols = Array.from(new Set(list.flatMap((r) => Object.keys(r)))).filter((c) => !HIDDEN.has(c));
        return (
          <section key={k} aria-label={human(k)}>
            <h3>{human(k)} <span className={styles.muted}>({list.length})</span></h3>
            {list.length ? (
              <table className={styles.table}>
                <thead><tr>{cols.map((c) => <th key={c} scope="col">{human(c)}</th>)}</tr></thead>
                <tbody>{list.map((r, i) => <tr key={i}>{cols.map((c) => <td key={c}><Cell v={r[c]} /></td>)}</tr>)}</tbody>
              </table>
            ) : <p className={styles.muted}>Nothing found.</p>}
          </section>
        );
      })}
      {lists.map(([k, v]) => <section key={k} aria-label={human(k)}><h3>{human(k)}</h3><p><Cell v={v} /></p></section>)}
      {groups.map(([k, v]) => <section key={k} aria-label={human(k)}><h3>{human(k)}</h3><InsightResult data={v as Record<string, unknown>} /></section>)}
    </div>
  );
}

export function Insights() {
  const { connectionId } = useSuite();
  const params = useSearchParams();
  const router = useRouter();
  const path = usePathname() ?? "";
  const [cards, setCards] = useState<InsightCard[]>([]);
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const key = params?.get("show") ?? "";
  useEffect(() => { insightsApi.list(connectionId).then((r) => setCards(r.insights), (e: unknown) => setError(errText(e))); }, [connectionId]);
  useEffect(() => { setData(null); setError(null); }, [key]);
  const card = cards.find((c) => c.key === key);
  const inputs = INPUTS[key] ?? [];
  async function look(e?: FormEvent<HTMLFormElement>) {
    e?.preventDefault();
    const q: Record<string, string> = {};
    if (e) new FormData(e.currentTarget).forEach((v, k) => { if (String(v).trim()) q[k] = String(v).trim(); });
    setBusy(true); setError(null);
    try { setData(await insightsApi.get(connectionId, key, q)); } catch (err) { setError(errText(err)); } finally { setBusy(false); }
  }
  return (
    <>
      <PageHead title="Look closer" purpose="Questions about this database, answered from its own records. These only read; changes happen in Change records or Set up." />
      <nav aria-label="Insights" className={styles.row}>
        {cards.map((c) => (
          <a key={c.key} href={`${path}?show=${c.key}`} aria-current={c.key === key ? "page" : undefined}
            onClick={(e) => { e.preventDefault(); router.push(`${path}?show=${c.key}`); }}>{c.title}</a>
        ))}
      </nav>
      {!card ? (
        <ul className={styles.list} data-testid="insight-list">
          {cards.map((c) => <li key={c.key}><strong>{c.title}</strong>. {c.what}</li>)}
        </ul>
      ) : (
        <section className={styles.section} aria-labelledby="insight-h">
          <h2 id="insight-h">{card.title}</h2>
          <p className={styles.muted}>{card.what}</p>
          <form onSubmit={(e) => void look(e)} className={styles.row} data-testid="insight-form">
            {inputs.map((i) => (
              <label key={i.name}>{i.label}
                <input name={i.name} placeholder={i.placeholder} required={i.required} inputMode={/id|days|mb/.test(i.name) ? "numeric" : undefined} />
              </label>
            ))}
            <Button type="submit" size="sm" loading={busy}>Look</Button>
          </form>
          {error ? <Status tone="danger">{error}</Status> : null}
          {busy && !data ? <Status tone="busy">Reading…</Status> : null}
          {data ? <InsightResult data={data} /> : null}
        </section>
      )}
    </>
  );
}
