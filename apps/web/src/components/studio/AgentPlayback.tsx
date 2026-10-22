"use client";

import { useState } from "react";
import type { StudioAppDesign } from "@/lib/studio-session";
import { studioAgentApi } from "@/lib/api/studio-agent";

export type PlaybackQuestion = { id: string; question: string; options: string[]; default?: string; answer?: string };
export type Playback = {
  wants?: { need: string; quote?: string; quoted?: boolean }[];
  reuses?: { app_or_model: string; for?: string; why_it_fits?: string }[];
  new?: { thing: string; why?: string }[];
  left_out?: { item: string; why?: string }[];
  questions?: PlaybackQuestion[];
};
type WithPlayback = StudioAppDesign & { playback?: Playback };

export function playbackOf(design: StudioAppDesign): Playback | null {
  const pb = (design as WithPlayback).playback;
  return pb && typeof pb === "object" && (pb.wants?.length || pb.reuses?.length || pb.new?.length) ? pb : null;
}

/** One-tap answer: stored on the design and sent with Build like any other edit. */
export function answerQuestion(design: StudioAppDesign, id: string, answer: string): StudioAppDesign {
  const pb = playbackOf(design);
  if (!pb) return design;
  const questions = (pb.questions || []).map((q) => (q.id === id ? { ...q, answer } : q));
  return { ...(design as WithPlayback), playback: { ...pb, questions } } as StudioAppDesign;
}

/** Agent mode playback: what we heard, what we reuse and why, what is new, what is left out. */
/** What the owner changed: answers that differ from the default, and edited assumptions. */
export function pendingEdits(design: StudioAppDesign) {
  const pb = playbackOf(design);
  const answers: Record<string, string> = {};
  for (const q of pb?.questions || []) if (q.answer && q.answer !== q.default) answers[q.id] = q.answer;
  const assumptions = (design.assumptions || [])
    .filter((a) => a.chosen)
    .map((a) => ({ id: a.requirement_id || "", text: a.text, chosen: a.chosen }));
  return { answers, assumptions, count: Object.keys(answers).length + assumptions.length };
}

export function AgentPlayback({
  design,
  onChange,
  sessionId,
}: {
  design: StudioAppDesign;
  onChange?: (next: StudioAppDesign) => void;
  /** When set, owner edits can be sent back to the agent for a re-design. */
  sessionId?: string;
}) {
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pb = playbackOf(design);
  if (!pb) return null;
  const edits = pendingEdits(design);
  async function redesign() {
    if (!sessionId || !edits.count) return;
    setUpdating(true);
    setError(null);
    try {
      const res = await studioAgentApi.agentRedesign(sessionId, edits.answers, edits.assumptions);
      onChange?.(res.design);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't update the design. Try again.");
    } finally {
      setUpdating(false);
    }
  }
  return (
    <div className="diagnosis-field" data-testid="studio-agent-playback">
      <span>Here is what we understood</span>
      {pb.wants?.length ? (
        <ul className="diagnosis-facts" data-testid="playback-wants">
          {pb.wants.map((w, i) => (
            <li key={`w${i}`}>
              {w.need}
              {w.quote && w.quoted ? <em className="clarify-help"> — &ldquo;{w.quote}&rdquo;</em> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {pb.reuses?.length ? (
        <>
          <span>Already in your Odoo, reused</span>
          <ul className="diagnosis-facts" data-testid="playback-reuses">
            {pb.reuses.map((r, i) => (
              <li key={`r${i}`}>
                <strong>{r.app_or_model}</strong>
                {r.for ? ` for ${r.for}` : ""}
                {r.why_it_fits ? <span className="clarify-help"> — {r.why_it_fits}</span> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {pb.new?.length ? (
        <>
          <span>New for you</span>
          <ul className="diagnosis-facts" data-testid="playback-new">
            {pb.new.map((n, i) => (
              <li key={`n${i}`}>
                {n.thing}
                {n.why ? <span className="clarify-help"> — {n.why}</span> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {pb.left_out?.length ? (
        <>
          <span>Left out for now</span>
          <ul className="diagnosis-facts" data-testid="playback-left-out">
            {pb.left_out.map((l, i) => (
              <li key={`l${i}`}>
                {l.item}
                {l.why ? <span className="clarify-help"> — {l.why}</span> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {pb.questions?.length ? (
        <div data-testid="playback-questions">
          <span>A few quick questions (we picked a default)</span>
          {pb.questions.slice(0, 3).map((q) => {
            const chosen = q.answer || q.default || "";
            return (
              <div key={q.id} className="clarify-help">
                <p>{q.question}</p>
                {q.options.map((o) => (
                  <button
                    key={o}
                    type="button"
                    className={`btn btn-sm ${o === chosen ? "btn-primary" : "btn-secondary"}`}
                    aria-pressed={o === chosen}
                    disabled={!onChange}
                    onClick={() => onChange?.(answerQuestion(design, q.id, o))}
                  >
                    {o}
                  </button>
                ))}
              </div>
            );
          })}
        </div>
      ) : null}
      {sessionId && onChange && edits.count ? (
        <div data-testid="playback-redesign">
          <button type="button" className="btn btn-primary btn-sm" disabled={updating} onClick={() => void redesign()}>
            {updating ? "Updating the design…" : `Update the design with your ${edits.count === 1 ? "change" : `${edits.count} changes`}`}
          </button>
          {error ? <p className="clarify-help" role="alert">{error}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
