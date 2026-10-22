"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";

type Pack = {
  summary: string;
  qa: Array<{ question: string; asked_by?: string; answer: string[]; confidence?: string }>;
  to_confirm: string[];
  starter_plan: Array<{ step: number; app: string; why: string }>;
  follow_up_email: { subject: string; body: string; sent: false };
  note: string;
};

/** Q7: after the meeting — summary, Q&A, a follow-up email draft you copy (never sent), starter plan. */
export function AfterMeetingPanel({ sessionId }: { sessionId: string }) {
  const [pack, setPack] = useState<Pack | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    api.liveDemoCopilotAfterMeeting(sessionId).then(setPack, (e: Error) => setError(e.message));
  }, [sessionId]);
  if (error) return <p className="text-sm text-danger" role="alert">The meeting notes didn&apos;t load: {error}</p>;
  if (!pack) return <p className="text-sm text-muted" role="status">Putting the meeting notes together…</p>;
  return (
    <section className="mt-6 space-y-4" data-testid="ldc-after-meeting">
      <h2 className="text-base font-semibold text-ink">After the meeting</h2>
      <p className="text-sm text-ink">{pack.summary}</p>
      {pack.qa.length ? (
        <div>
          <h3 className="text-sm font-semibold text-ink">Questions and answers</h3>
          <ul className="mt-1 space-y-2">
            {pack.qa.map((q, i) => (
              <li key={i} className="text-sm">
                <p className="font-medium text-ink">{q.question}</p>
                <ul className="ml-4 list-disc text-muted">
                  {q.answer.map((b, j) => (
                    <li key={j}>{b}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {pack.to_confirm.length ? (
        <div>
          <h3 className="text-sm font-semibold text-ink">To confirm with the client</h3>
          <ul className="ml-4 list-disc text-sm text-muted">
            {pack.to_confirm.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {pack.starter_plan.length ? (
        <div>
          <h3 className="text-sm font-semibold text-ink">Starter plan</h3>
          <ol className="ml-4 list-decimal text-sm">
            {pack.starter_plan.map((p) => (
              <li key={p.step}>
                <strong>{p.app}</strong> <span className="text-muted">— {p.why}</span>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
      <div>
        <h3 className="text-sm font-semibold text-ink">Follow-up email (draft)</h3>
        <p className="text-xs text-muted">{pack.note}</p>
        <pre className="hairline mt-2 whitespace-pre-wrap rounded-md p-3 text-sm" data-testid="ldc-followup-body">
          <strong>{pack.follow_up_email.subject}</strong>
          {"\n\n"}
          {pack.follow_up_email.body}
        </pre>
        <Button
          size="sm"
          variant="secondary"
          className="mt-2"
          onClick={() => {
            void navigator.clipboard?.writeText(`${pack.follow_up_email.subject}\n\n${pack.follow_up_email.body}`);
            setCopied(true);
          }}
        >
          {copied ? "Copied" : "Copy the draft"}
        </Button>
      </div>
    </section>
  );
}
