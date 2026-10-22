"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { upkeepApi, type FileCheck, type FileScan, type Schedule } from "@/lib/api/suite";
import { errText, useSuite } from "./SuiteContext";
import { PageHead, Status } from "./parts";
import styles from "./Suite.module.css";
import { Term } from "@/components/ui/Term";

const AREAS = { schedules: "Scheduled actions", files: "Files and storage" } as const;
type Area = keyof typeof AREAS;

export function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

function Tabs({ active }: { active: Area }) {
  const { connectionId } = useSuite();
  return (
    <nav aria-label="Upkeep" className={styles.row}>
      {(Object.keys(AREAS) as Area[]).map((k) => <Link key={k} href={`/connections/${connectionId}/suite/upkeep/${k}`} aria-current={k === active ? "page" : undefined}>{AREAS[k]}</Link>)}
    </nav>
  );
}

export function Upkeep({ area }: { area: string }) {
  const a = (area in AREAS ? area : "schedules") as Area;
  return a === "files" ? <Files /> : <Schedules />;
}

function Schedules() {
  const { connectionId } = useSuite();
  const [rows, setRows] = useState<Schedule[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pausing, setPausing] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => { upkeepApi.schedules(connectionId).then((r) => setRows(r.schedules), (e: unknown) => setError(errText(e))); }, [connectionId]);
  useEffect(() => { load(); }, [load]);
  const hours = useMemo(() => {
    const now = Date.now();
    const slots = Array.from({ length: 24 }, () => 0);
    for (const s of rows ?? []) for (const t of s.next_24h) { const h = Math.floor((new Date(t).getTime() - now) / 3_600_000); if (h >= 0 && h < 24) slots[h] += 1; }
    return slots;
  }, [rows]);
  async function act(fn: () => Promise<unknown>) {
    setBusy(true); setError(null);
    try { await fn(); load(); } catch (e) { setError(errText(e)); } finally { setBusy(false); }
  }
  const failing = (rows ?? []).filter((r) => r.failing).length;
  return (
    <>
      <PageHead title="Scheduled actions" purpose="What runs on its own, in plain words: when it runs next, how the last run went, and who paused it and why." />
      <Tabs active="schedules" />
      {error ? <Status tone="danger">{error}</Status> : null}
      {!rows ? <Status tone="busy">Reading…</Status> : (
        <>
          <p>{rows.filter((r) => r.active).length} running · {rows.filter((r) => !r.active).length} paused or off · {failing} failing</p>
          <section className={styles.section} aria-labelledby="tl-h">
            <h2 id="tl-h">Next 24 hours</h2>
            <ol className={styles.row} aria-label="Runs per hour" data-testid="upkeep-timeline">
              {hours.map((n, i) => <li key={i} className={n ? undefined : styles.muted} title={`In ${i} to ${i + 1} hours: ${n} runs`}>+{i}h: {n}</li>)}
            </ol>
          </section>
          <table className={styles.table} data-testid="upkeep-schedules">
            <thead><tr><th scope="col">Name</th><th scope="col">What it does</th><th scope="col">How often</th><th scope="col">Next run</th><th scope="col">Last run</th><th scope="col"><span className={styles.muted}>Actions</span></th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} data-testid={`cron-${r.id}`}>
                  <td>{r.name}</td>
                  <td data-testid="cron-description">{r.description}{r.description_source !== "catalogue" ? <div className={styles.muted}>{r.description_source === "plain fallback" ? "Plain summary from its schedule" : "Suggested wording, checked by code"}</div> : null}</td>
                  <td>{r.how_often}</td>
                  <td>{r.active && r.next_run ? new Date(`${r.next_run.replace(" ", "T")}Z`).toLocaleString() : "Not scheduled"}</td>
                  <td>{r.failing ? <Status tone="warning">{r.last_result}</Status> : r.last_result}</td>
                  <td>
                    {r.paused ? <div className={styles.muted}>Paused by {r.paused.by} at {new Date(r.paused.at).toLocaleString()}: {r.paused.reason}</div> : null}
                    {r.active ? (pausing === r.id ? (
                      <form className={styles.row} onSubmit={(e) => { e.preventDefault(); if (reason.trim().length >= 3) void act(async () => { await upkeepApi.pause(connectionId, r.id, reason.trim()); setPausing(null); setReason(""); }); }}>
                        <input aria-label="Why pause it" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why" autoFocus />
                        <Button size="sm" type="submit" loading={busy} disabled={reason.trim().length < 3}>Pause</Button>
                        <Button size="sm" variant="secondary" type="button" onClick={() => setPausing(null)}>Cancel</Button>
                      </form>
                    ) : <Button size="sm" variant="secondary" onClick={() => setPausing(r.id)}>Pause</Button>)
                      : <Button size="sm" variant="secondary" loading={busy} onClick={() => void act(() => upkeepApi.resume(connectionId, r.id))}>Resume</Button>}
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

function Files() {
  const { connectionId } = useSuite();
  const [scan, setScan] = useState<FileScan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [check, setCheck] = useState<FileCheck | null>(null);
  const [done, setDone] = useState<{ run_id: string; removed: number; space_freed: number } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const load = useCallback(() => { upkeepApi.files(connectionId).then(setScan, (e: unknown) => setError(errText(e))); }, [connectionId]);
  useEffect(() => { load(); }, [load]);
  const toggle = (id: number, on: boolean) => { setCheck(null); setPicked((p) => { const n = new Set(p); if (on) n.add(id); else n.delete(id); return n; }); };
  async function act(name: string, fn: () => Promise<unknown>) {
    setBusy(name); setError(null);
    try { await fn(); } catch (e) { setError(errText(e)); } finally { setBusy(null); }
  }
  return (
    <>
      <PageHead title="Files and storage" purpose="What takes space and what can go. Figures are measured: a file stored twice takes space once, so space only comes back when every copy goes." />
      <Tabs active="files" />
      {error ? <Status tone="danger">{error}</Status> : null}
      {!scan ? <Status tone="busy">Measuring…</Status> : (
        <>
          <p data-testid="files-totals">{scan.files} files · {bytes(scan.stored_bytes)} stored · {scan.accounting_excluded} files on accounting documents are never offered</p>
          <section className={styles.section} aria-labelledby="bd-h">
            <h2 id="bd-h">Where the space goes</h2>
            <table className={styles.table}><thead><tr><th scope="col"><Term tech="ir.model">Record type</Term></th><th scope="col">Files</th><th scope="col">Size</th></tr></thead>
              <tbody>{scan.breakdown.slice(0, 12).map((b) => <tr key={b.model || "none"}><td>{b.model || "Not attached to anything"}</td><td>{b.files}</td><td>{bytes(b.bytes)}</td></tr>)}</tbody></table>
          </section>
          <section className={styles.section} aria-labelledby="cl-h">
            <h2 id="cl-h">Can be cleaned</h2>
            <h3>Not attached to anything ({scan.unattached.length})</h3>
            <ul className={styles.list}>{scan.unattached.slice(0, 100).map((u) => <li key={u.id}><label className={styles.row}><input type="checkbox" checked={picked.has(u.id)} onChange={(e) => toggle(u.id, e.target.checked)} /> {u.name} <span className={styles.muted}>{bytes(u.size)}</span></label></li>)}</ul>
            <h3>The same file more than once ({scan.repeats.length})</h3>
            <ul className={styles.list}>{scan.repeats.slice(0, 100).map((r) => (
              <li key={r.checksum}>{r.all.length} copies of {bytes(r.size)}, keeps #{r.keep}
                {r.copies.map((c) => <label key={c} className={styles.row}><input type="checkbox" checked={picked.has(c)} onChange={(e) => toggle(c, e.target.checked)} /> Copy #{c}</label>)}
              </li>
            ))}</ul>
            <div className={styles.row}>
              <Button variant="secondary" disabled={!picked.size} loading={busy === "check"} onClick={() => act("check", async () => setCheck(await upkeepApi.checkFiles(connectionId, [...picked])))} data-testid="files-check">Check {picked.size} files</Button>
              <Button variant="primary" disabled={!check?.ready} loading={busy === "clean"} onClick={() => act("clean", async () => { setDone(await upkeepApi.cleanFiles(connectionId, check!.verdicts.filter((v) => v.verdict === "ready").map((v) => v.id))); setCheck(null); setPicked(new Set()); load(); })} data-testid="files-clean">Clean {check?.ready ?? 0} files</Button>
            </div>
            {check ? (
              <div data-testid="files-check-report">
                <Status tone="info">{check.ready} ready · {check.blocked} blocked · frees {bytes(check.space_freed)}. {check.note}</Status>
                <ul className={styles.list}>{check.verdicts.filter((v) => v.verdict === "blocked").map((v) => <li key={v.id}><Status tone="warning">{v.name ?? `#${v.id}`}: {v.reason}</Status></li>)}</ul>
              </div>
            ) : null}
            {done ? (
              <Status tone="success">Removed {done.removed} files and freed {bytes(done.space_freed)}. A copy of each is kept in an archive.{" "}
                <button type="button" className={styles.linkBtn} onClick={() => act("undo", async () => { await upkeepApi.undoClean(connectionId, done.run_id); setDone(null); load(); })}>Put them back</button>
              </Status>
            ) : null}
          </section>
        </>
      )}
    </>
  );
}
