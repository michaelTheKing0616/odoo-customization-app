"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { PresenterOverlay, type PresenterSseStatus } from "@/components/live-demo-copilot/PresenterOverlay";
import { Callout } from "@/components/ui/Callout";
import { api, getApiBase, type LiveDemoAnswer } from "@/lib/api";

function PresenterOverlayPageInner() {
  const search = useSearchParams();
  const sessionId = search.get("session")?.trim() || "";
  const [answers, setAnswers] = useState<LiveDemoAnswer[]>([]);
  const [sseStatus, setSseStatus] = useState<PresenterSseStatus>("connecting");
  const [error, setError] = useState<string | null>(null);

  const refreshAnswers = useCallback(async (sid: string) => {
    try {
      const res = await api.liveDemoCopilotAnswers(sid);
      setAnswers(res.answers);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    void refreshAnswers(sessionId);
  }, [sessionId, refreshAnswers]);

  useEffect(() => {
    if (!sessionId) return;
    const base = getApiBase();
    let es: EventSource | null = null;
    let closed = false;
    let retryTimer: number | undefined;

    function connect() {
      if (closed) return;
      setSseStatus("connecting");
      es = new EventSource(`${base}/api/live-demo-copilot/sessions/${sessionId}/events`);
      es.onopen = () => setSseStatus("connected");
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as { type?: string };
          if (data.type === "answer") {
            void refreshAnswers(sessionId);
          }
        } catch {
          /* ignore */
        }
      };
      es.onerror = () => {
        setSseStatus("disconnected");
        es?.close();
        retryTimer = window.setTimeout(connect, 2000);
      };
    }

    connect();
    return () => {
      closed = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      es?.close();
    };
  }, [sessionId, refreshAnswers]);

  if (!sessionId) {
    return (
      <div className="mx-auto max-w-md p-6">
        <Callout variant="danger" title="Missing session">
          Open this overlay from a Live Demo Co-Pilot session (Open presenter overlay).
        </Callout>
      </div>
    );
  }

  return (
    <>
      {error ? (
        <div className="px-4 pt-3">
          <Callout variant="danger" title="Could not load answers">
            {error}
          </Callout>
        </div>
      ) : null}
      <PresenterOverlay answers={answers} sseStatus={sseStatus} sessionId={sessionId} />
    </>
  );
}

export default function PresenterOverlayPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center text-sm text-muted">
          Opening presenter overlay…
        </div>
      }
    >
      <PresenterOverlayPageInner />
    </Suspense>
  );
}
