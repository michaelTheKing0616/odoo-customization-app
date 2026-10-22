"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { useSuite } from "./SuiteContext";
import { PageHead, PassportCard, Status } from "./parts";
import styles from "./Suite.module.css";

/** Suite home (spec 4.2): what is this database, what needs me, what changed. Only real checks. */
export function SuiteHome() {
  const { connectionId, home, error, reload } = useSuite();
  const s = `/connections/${connectionId}/suite`;
  if (error) return <Status tone="danger">Can&apos;t read this database: {error} <button type="button" className={styles.linkBtn} onClick={reload}>Try again</button></Status>;
  if (!home) return <Status tone="busy">Reading the database…</Status>;
  return (
    <>
      <PageHead title="Your Odoo" purpose="What this database is, what needs you, and what changed." />
      <div className={styles.grid2}>
        <PassportCard />
        <section className={styles.card} aria-label="Ask">
          <p className={styles.flush}><Link href={`${s}/ask`}>Ask about your Odoo</Link></p>
          <p className={styles.mutedLine}>Answers come from this database. Suggestions are proposals; code checks them before anything runs.</p>
        </section>
      </div>
      <section className={styles.section} aria-labelledby="needs-h" data-testid="suite-needs">
        <h2 id="needs-h">Needs you ({home.needs_you.length})</h2>
        {home.needs_you.length ? (
          <ul className={styles.list}>
            {home.needs_you.map((n, i) => (
              <li key={i} className={styles.row}><Status tone="warning">{n.text}</Status> <Link href={n.href}>Open</Link></li>
            ))}
          </ul>
        ) : (
          <div className={styles.row}><Status tone="success">Nothing needs you right now.</Status><Button variant="ghost" size="sm" onClick={reload}>Check again</Button></div>
        )}
      </section>
      <div className={styles.grid2}>
        <section className={styles.card} aria-labelledby="recent-h">
          <h2 id="recent-h">Recent setup runs</h2>
          {home.recent_runs.length ? (
            <ul className={styles.list}>
              {home.recent_runs.map((r) => (
                <li key={r.id}><Link href={`${s}/setup?run=${r.id}&view=run`}>{r.name}</Link> <span className={styles.muted}>{r.state}{r.kind === "undo" ? " (undo)" : ""}</span></li>
              ))}
            </ul>
          ) : <p className={styles.muted}>No runs yet. <Link href={`${s}/setup`}>Set up this database</Link></p>}
        </section>
        <section className={styles.card} aria-labelledby="money-h">
          <h2 id="money-h">Money guard</h2>
          <p className={styles.flush}>{home.facts.posted_entries} posted entries · {home.facts.done_moves} done stock moves</p>
          <p className={styles.mutedLine}>{home.facts.posted_entries ? "Installs, country packages, currency and costing changes are closed on this database." : "No posted entries yet: installs and the country package can still run."}</p>
          <p className={styles.mutedLine}><Link href={`${s}/safety/money`}>See the rules</Link></p>
        </section>
      </div>
    </>
  );
}
