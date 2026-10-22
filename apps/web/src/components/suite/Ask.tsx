"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { upkeepApi, type AskAnswer, type Guide } from "@/lib/api/suite";
import { errText, useSuite } from "./SuiteContext";
import { BotAvatar, type BotState } from "./BotAvatar";
import { Spokes } from "@/components/loading-ui/spokes";
import { PageHead, Status } from "./parts";
import styles from "./Suite.module.css";

const REVERSIBLE: Record<string, string> = { easy: "Easy to change later", hard: "Hard to change later", after_posting_no: "Can't change once entries are posted" };

export function planWords(a: Extract<AskAnswer, { kind: "plan" }>): string {
  const c = a.plan.change;
  const what = c.tool === "transitions" ? `press ${c.button}` : `set ${c.field} to ${typeof c.value === "object" && c.value ? String((c.value as { ref?: string }).ref) : String(c.value)}`;
  const which = a.plan.filters.length ? ` where ${a.plan.filters.map((f) => f.map((x) => (Array.isArray(x) ? x.join(" or ") : String(x))).join(" ")).join(" and ")}` : "";
  return `On ${a.plan.label}${which}: ${what}.`;
}

/** Ask (spec 9): answers come from this database. Money questions go to Odoo's own screens; changes become a plan you check first. */
export function Ask() {
  const { connectionId } = useSuite();
  const router = useRouter();
  const [text, setText] = useState("");
  const [answer, setAnswer] = useState<AskAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [topics, setTopics] = useState<{ key: string; label: string }[]>([]);
  const [guide, setGuide] = useState<Guide | null>(null);
  // 105/112: live steps from the real pipeline; typing a new request redirects; Esc stops.
  const [steps, setSteps] = useState<string[]>([]);
  const [stopped, setStopped] = useState(false);
  const ctrl = useRef<AbortController | null>(null);
  const runAsk = useCallback(async (q: string, redirected: boolean) => {
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    setSteps(redirected ? [`Changed course: ${q}`] : []);
    setStopped(false);
    setAnswer(null);
    setBusy("ask");
    setError(null);
    try {
      const a = await upkeepApi.askStream(connectionId, q, (t) => setSteps((prev) => [...prev, t]), c.signal);
      if (ctrl.current === c) setAnswer(a);
    } catch (e) {
      if (!c.signal.aborted) setError(errText(e));
    } finally {
      if (ctrl.current === c) {
        ctrl.current = null;
        setBusy(null);
      }
    }
  }, [connectionId]);
  const stop = useCallback(() => {
    if (!ctrl.current) return;
    ctrl.current.abort();
    ctrl.current = null;
    setBusy(null);
    setStopped(true);
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && ctrl.current) { e.preventDefault(); stop(); } };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); ctrl.current?.abort(); };
  }, [stop]);
  useEffect(() => { upkeepApi.guideTopics(connectionId).then((r) => setTopics(r.topics), () => undefined); }, [connectionId]);
  async function act(name: string, fn: () => Promise<unknown>) {
    setBusy(name); setError(null);
    try { await fn(); } catch (e) { setError(errText(e)); } finally { setBusy(null); }
  }
  return (
    <>
      <PageHead title="Ask" purpose="Ask for a change in your own words. Code checks every name against this database; anything that would change data becomes a plan you check first." />
      <form className={styles.row} onSubmit={(e) => { e.preventDefault(); if (text.trim().length > 1) void runAsk(text.trim(), busy === "ask"); }}>
        <label htmlFor="suite-ask" className={styles.grow}>
          <span className={styles.muted}>For example: confirm all the sent quotations, or set payment terms to 30 Days on quotations</span>
          <input id="suite-ask" value={text} onChange={(e) => setText(e.target.value)} style={{ inlineSize: "100%" }} data-testid="suite-ask-input" />
        </label>
        <BotAvatar bot="expert" size={32} state={askState(busy === "ask", error, answer, steps.length > 0)} />
        {busy === "ask" ? (
          <>
            <Button type="submit" variant="secondary" data-testid="suite-ask-redirect">Change course</Button>
            <Button type="button" variant="ghost" onClick={stop} data-testid="suite-ask-stop">Stop (Esc)</Button>
          </>
        ) : (
          <Button type="submit" variant="primary">Ask</Button>
        )}
      </form>
      {busy === "ask" || steps.length ? (
        busy === "ask" ? (
          <ol className="ask-steps" aria-live="polite" data-testid="suite-ask-steps">
            {steps.map((t, i) => <li key={`${i}-${t}`} data-state="done">{t}</li>)}
            <li data-state="running"><Spokes aria-hidden className="ask-step-spin" /> Working</li>
          </ol>
        ) : (
          <details className="ask-steps-folded" data-testid="suite-ask-steps">
            <summary>{stopped ? "Stopped. Ask never changes data, so nothing was changed." : `${steps.length} ${steps.length === 1 ? "step" : "steps"}`}</summary>
            <ol className="ask-steps">{steps.map((t, i) => <li key={`${i}-${t}`} data-state="done">{t}</li>)}</ol>
          </details>
        )
      ) : null}
      {error ? <Status tone="danger">{error}</Status> : null}
      {answer ? (
        <section className={styles.card} aria-live="polite" data-testid="suite-ask-answer">
          {answer.kind === "money" ? <Status tone="info">{answer.answer}</Status> : null}
          {answer.kind === "unclear" ? <Status tone="warning">{answer.unclear}</Status> : null}
          {answer.kind === "plan" ? (
            <>
              <p className={styles.flush}>{planWords(answer)}</p>
              {answer.dropped.length ? <p className={styles.mutedLine}>Left out because this database doesn&apos;t have them: {answer.dropped.join(", ")}</p> : null}
              <div className={styles.row}>
                <Button variant="primary" loading={busy === "fix"} onClick={() => void act("fix", async () => { const t = await upkeepApi.ticket(connectionId, answer.plan); router.push(t.next); })} data-testid="suite-fix-it">Fix it: open as a batch to check</Button>
              </div>
            </>
          ) : null}
          {"source" in answer ? <p className={styles.mutedLine}>Read by: {answer.source}{"timing" in answer && answer.timing?.cached ? <span className="instant-tag" data-testid="suite-instant" title="Answered from a saved answer, so no AI cost">Instant, {answer.timing.seconds.toFixed(2)} s, free</span> : null}</p> : null}
        </section>
      ) : null}
      <section className={styles.section} aria-labelledby="dg-h">
        <h2 id="dg-h">Help me decide</h2>
        <div className={styles.row}>{topics.map((t) => <Button key={t.key} size="sm" variant="secondary" loading={busy === t.key} onClick={() => void act(t.key, async () => setGuide(await upkeepApi.guide(connectionId, t.key)))}>{t.label}</Button>)}</div>
        {guide ? (
          <div className={styles.card} data-testid="suite-guide">
            {guide.decided ? <Status tone="info">{guide.decided}</Status> : (
              <>
                <p className={styles.flush}><strong>{guide.question}</strong></p>
                {guide.why_asking ? <p className={styles.mutedLine}>{guide.why_asking}</p> : null}
                <ul className={styles.list}>{guide.options.map((o) => <li key={o.label}><strong>{o.label}</strong>: {o.what_changes} <span className={styles.tag}>{REVERSIBLE[o.reversible]}</span></li>)}</ul>
              </>
            )}
            <p className={styles.mutedLine}>From this database: {guide.facts.map((f) => `${f.label} ${String(f.value)}`).join(" · ")}</p>
          </div>
        ) : null}
      </section>
    </>
  );
}

function askState(asking: boolean, error: string | null, answer: AskAnswer | null, hasSteps = false): BotState {
  // 104: thinking until the pipeline reports its first real step, then working.
  if (asking) return hasSteps ? "working" : "thinking";
  if (error || answer?.kind === "unclear") return "needs_you";
  return answer ? "done" : "idle";
}
