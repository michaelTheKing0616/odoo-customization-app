"use client";

import { Button } from "@/components/ui/Button";
import { BOT_NAMES, BotAvatar, type Bot, type BotState } from "./BotAvatar";
import * as I from "@/components/ui/icons";
import { PageHead, SafetyLevel, Status } from "./parts";
import styles from "./Suite.module.css";

const ICONS = Object.entries(I) as [string, typeof I.IconExpert][];

/** Every state of the suite's parts on one page (spec 10, 12). Toggle the app theme to check light and dark. */
export function StatesPreview() {
  return (
    <div data-testid="suite-states">
      <PageHead title="States preview" purpose="Each part in every state, for checking light and dark." />
      <section className={styles.section} aria-labelledby="st-status">
        <h2 id="st-status">Status lines (never colour only: each has an icon and words)</h2>
        <div className={styles.list}>
          <Status tone="info">Scheduled: 12 messages go out on Tue 20 Oct, 09:00.</Status>
          <Status tone="busy">Running: 4 of 12 done.</Status>
          <Status tone="success">Finished: 12 done.</Status>
          <Status tone="warning">Cancelled before it was sent. Nothing went out.</Status>
          <Status tone="danger">Refused by the money guard: accounting records can&apos;t be messaged in bulk.</Status>
        </div>
      </section>
      <section className={styles.section} aria-labelledby="st-safety">
        <h2 id="st-safety">Safety levels</h2>
        <div className={styles.row}><SafetyLevel level="look" /><SafetyLevel level="undo" /><SafetyLevel level="hard" /><SafetyLevel level="never" /></div>
      </section>
      <section className={styles.section} aria-labelledby="st-controls">
        <h2 id="st-controls">Controls</h2>
        <div className={styles.row}>
          <Button>Check the batch</Button>
          <Button loading>Checking</Button>
          <Button disabled>Run (check first)</Button>
          <Button variant="danger">Cancel the send</Button>
          <button type="button" className={styles.linkBtn}>Cancel</button>
          <button type="button" className={styles.linkBtn} disabled>Cancel</button>
        </div>
        <div className={styles.row}>
          <label className={styles.row}>Normal <input defaultValue="Hello {name}" /></label>
          <label className={styles.row}>Disabled <input disabled defaultValue="Locked" /></label>
          <label className={styles.row}>Wrong <input aria-invalid="true" defaultValue="soon" /></label>
          <label className={styles.row}>Send at <input type="datetime-local" /></label>
        </div>
      </section>
      <section className={styles.section} aria-labelledby="st-cards">
        <h2 id="st-cards">Cards</h2>
        <div className={styles.grid2}>
          <div className={styles.card}>Plain</div>
          <div className={styles.card} data-interactive="true" tabIndex={0}>Can be chosen (hover, press, focus)</div>
          <div className={styles.card} data-interactive="true" data-selected="true" tabIndex={0}>Chosen</div>
        </div>
      </section>
      <section className={styles.section} aria-labelledby="st-load">
        <h2 id="st-load">Loading, empty, error</h2>
        <div className={styles.grid2}>
          <div className={styles.card} aria-busy="true" aria-label="Loading"><span className={styles.skeleton} /><span className={styles.skeleton} /><span className={styles.skeleton} /></div>
          <div className={styles.empty}><strong>No runs yet.</strong>Runs you start or schedule show here.</div>
          <div className={styles.errorBox}><Status tone="danger">Odoo didn&apos;t answer. Try again in a minute.</Status></div>
        </div>
      </section>
      <section className={styles.section} aria-labelledby="st-table">
        <h2 id="st-table">Table with numbers</h2>
        <table className={styles.table}>
          <thead><tr><th scope="col">Record</th><th scope="col">Result</th><th scope="col">Total</th></tr></thead>
          <tbody>
            <tr><td>Azure Interior</td><td>Done</td><td>1,204.00</td></tr>
            <tr><td>Deco Addict</td><td>Nothing to change</td><td>87.50</td></tr>
          </tbody>
        </table>
      </section>
      <section className={styles.section} aria-labelledby="st-bots">
        <h2 id="st-bots">Bot avatars (states: ready, thinking, working, done, needs you; sizes 16 to 48)</h2>
        <table className={styles.table}>
          <tbody>
            {(Object.keys(BOT_NAMES) as Bot[]).map((b) => (
              <tr key={b}>
                <th scope="row">{BOT_NAMES[b]}</th>
                {(["idle", "thinking", "working", "done", "needs_you"] as BotState[]).map((st) => <td key={st}><BotAvatar bot={b} state={st} size={32} /></td>)}
                <td><span className={styles.row}>{([16, 20, 24, 48] as const).map((z) => <BotAvatar key={z} bot={b} size={z} />)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className={styles.section} aria-labelledby="st-icons">
        <h2 id="st-icons">Keystone icons</h2>
        <ul className={`${styles.row} ${styles.plainList}`}>
          {ICONS.map(([name, Icon]) => <li key={name} className={styles.tag}><Icon aria-hidden width={14} height={14} /> {name.replace(/^Icon/, "")}</li>)}
        </ul>
      </section>
    </div>
  );
}
