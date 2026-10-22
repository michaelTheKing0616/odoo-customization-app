"use client";

import { AfterMeetingPanel } from "@/components/live-demo/AfterMeetingPanel";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Input } from "@/components/ui/Input";
import { PageHeader, Skeleton } from "@/components/ui/layout-primitives";
import { Badge } from "@/components/ui/Badge";
import { LiveDemoErrorNotice } from "@/components/live-demo-copilot/LiveDemoErrorNotice";
import { LiveDemoStageRail } from "@/components/live-demo-copilot/LiveDemoStageRail";
import { LiveDemoStateGuide } from "@/components/live-demo-copilot/LiveDemoStateGuide";
import {
  api,
  getApiBase,
  type LiveDemoCopilotDisclosure,
  type LiveDemoAnswer,
  type LiveDemoCopilotSession,
  type LiveDemoTranscriptLine,
} from "@/lib/api";
import {
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  consentReadyGuide,
  declinedLiveDemoGuide,
  emptyAnswersGuide,
  emptyLiveDemoGuide,
  emptyTranscriptGuide,
  liveDemoHonestyGuide,
  liveDemoStepFromState,
  liveJoinedGuide,
  meetingCreatedGuide,
  modeBadgeLabel,
  sanitizeLiveDemoCopy,
  waitingHostGuide,
  type LiveDemoErrorContext,
} from "@/lib/liveDemoCopilotScreen";
import "@/components/live-demo-copilot/live-demo-copilot-operate.css";

function statusBadgeVariant(
  severity: string | undefined,
): "default" | "success" | "warning" | "danger" | "info" {
  if (severity === "success") return "success";
  if (severity === "warning") return "warning";
  if (severity === "danger") return "danger";
  if (severity === "info") return "info";
  return "default";
}

function calloutVariant(
  severity: string | undefined,
): "info" | "warning" | "danger" {
  if (severity === "danger") return "danger";
  if (severity === "warning") return "warning";
  return "info";
}

export default function LiveDemoCopilotPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  const [disclosure, setDisclosure] = useState<LiveDemoCopilotDisclosure | null>(null);
  const [meetingUrl, setMeetingUrl] = useState("");
  const [botName, setBotName] = useState("Odoo Demo Co-Pilot");
  const [accepted, setAccepted] = useState(false);
  const [notified, setNotified] = useState(false);
  const [retentionOptIn, setRetentionOptIn] = useState(false);
  const [session, setSession] = useState<LiveDemoCopilotSession | null>(null);
  const [lines, setLines] = useState<LiveDemoTranscriptLine[]>([]);
  const [answers, setAnswers] = useState<LiveDemoAnswer[]>([]);
  const [mockText, setMockText] = useState("Can Odoo handle multi-company accounting?");
  const [presenterNames, setPresenterNames] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorContext, setErrorContext] = useState<LiveDemoErrorContext>("generic");
  const [feedHydrated, setFeedHydrated] = useState(true);

  useEffect(() => {
    api
      .liveDemoCopilotDisclosure()
      .then(setDisclosure)
      .catch((err: Error) => {
        setErrorContext("disclosure");
        setError(err.message);
      });
  }, []);

  const refreshTranscript = useCallback(async (sid: string) => {
    const tr = await api.liveDemoCopilotTranscript(sid);
    setLines(tr.lines);
  }, []);

  const refreshAnswers = useCallback(async (sid: string) => {
    const res = await api.liveDemoCopilotAnswers(sid);
    setAnswers(res.answers);
  }, []);

  const [freshId, setFreshId] = useState<string | null>(null);
  /** "Fresh answer": regenerate one answer, skipping the AI cache. */
  const freshAnswer = useCallback(async (sid: string, answerId: string) => {
    setFreshId(answerId);
    try {
      const row = await api.liveDemoCopilotRefreshAnswer(sid, answerId);
      setAnswers((prev) => prev.map((x) => (x.id === row.id ? row : x)));
    } finally {
      setFreshId(null);
    }
  }, []);

  useEffect(() => {
    if (!session?.id) {
      setLines([]);
      setAnswers([]);
      setFeedHydrated(true);
      return;
    }
    setFeedHydrated(false);
    Promise.all([refreshTranscript(session.id), refreshAnswers(session.id)])
      .catch((err: Error) => {
        setErrorContext("feed");
        setError(err.message);
      })
      .finally(() => setFeedHydrated(true));
  }, [session?.id, refreshTranscript, refreshAnswers]);

  useEffect(() => {
    if (!session?.id) return;
    const base = getApiBase();
    const es = new EventSource(`${base}/api/live-demo-copilot/sessions/${session.id}/events`);
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as { type?: string };
        if (data.type === "transcript") {
          void refreshTranscript(session.id);
        } else if (data.type === "answer") {
          void refreshAnswers(session.id);
        } else if (data.type === "status") {
          void api.liveDemoCopilotGetSession(session.id).then(setSession);
        }
      } catch {
        /* ignore malformed */
      }
    };
    return () => es.close();
  }, [session?.id, refreshTranscript, refreshAnswers]);

  const canLaunch = useMemo(
    () => Boolean(session && session.disclosure_accepted && !session.declined && !session.attendee_bot_id),
    [session],
  );

  const botJoined = Boolean(session?.attendee_bot_id);
  const status = session?.bot_status;
  const step = liveDemoStepFromState({
    hasSession: Boolean(session),
    declined: Boolean(session?.declined),
    consentAccepted: Boolean(session?.disclosure_accepted && !session?.declined),
    botJoined,
    hasLiveFeed: answers.length > 0 || lines.length > 0,
  });

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const speakers = presenterNames
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const created = await api.liveDemoCopilotCreateSession({
        meeting_url: meetingUrl.trim(),
        bot_name: botName.trim() || "Odoo Demo Co-Pilot",
        connection_id: connectionId,
        presenter_speakers: speakers,
      });
      setSession(created);
      setPresenterNames((created.presenter_speakers || []).join(", "));
      setLines([]);
      setAnswers([]);
    } catch (err) {
      setErrorContext("create");
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onConsent(accept: boolean) {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.liveDemoCopilotConsent(session.id, {
        disclosure_accepted: accept && accepted,
        attendees_notified: accept && notified,
        retention_opt_in: accept ? retentionOptIn : false,
        disclosure_version: disclosure?.version,
      });
      setSession(next);
      if (next.declined) {
        setErrorContext("consent");
        setError("Session declined - no bot will join and no audio will be processed.");
      }
    } catch (err) {
      setErrorContext("consent");
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onLaunch() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.liveDemoCopilotLaunch(session.id);
      setSession(next);
    } catch (err) {
      setErrorContext("launch");
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onLeave() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.liveDemoCopilotLeave(session.id);
      setSession(next);
    } catch (err) {
      setErrorContext("leave");
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  // Q7: the self-hosted bot is polled — every 4 s while it is in the call, pull status and new transcript lines.
  const liveBotId = session && !session.mock_mode ? session.attendee_bot_id : null;
  const liveState = session?.bot_state;
  useEffect(() => {
    if (!session || !liveBotId || !["joining", "waiting_room", "joined_recording", "joined_not_recording"].includes(String(liveState))) return;
    const id = window.setInterval(() => {
      api.liveDemoCopilotRefreshStatus(session.id).then(setSession, () => undefined);
    }, 4000);
    return () => window.clearInterval(id);
  }, [session?.id, liveBotId, liveState]); // eslint-disable-line react-hooks/exhaustive-deps

  async function onRefreshStatus() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.liveDemoCopilotRefreshStatus(session.id);
      setSession(next);
    } catch (err) {
      setErrorContext("status");
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onRetryLeavePurge() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.liveDemoCopilotRetryLeavePurge(session.id);
      setSession(next);
    } catch (err) {
      setErrorContext("leave");
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onMockUtterance() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      await api.liveDemoCopilotMockUtterance(session.id, {
        speaker_name: "Client",
        text: mockText.trim(),
      });
      await refreshTranscript(session.id);
    } catch (err) {
      setErrorContext("feed");
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function savePresenterNames() {
    if (!session?.id) return;
    setBusy(true);
    setError(null);
    try {
      const speakers = presenterNames
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const updated = await api.liveDemoCopilotSetPresenterSpeakers(session.id, speakers);
      setSession(updated);
      setPresenterNames((updated.presenter_speakers || []).join(", "));
    } catch (err) {
      setErrorContext("generic");
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function openPresenterOverlay() {
    if (!session?.id) return;
    const url = `/live-demo-copilot/overlay?session=${encodeURIComponent(session.id)}&connection=${encodeURIComponent(connectionId)}`;
    const win = window.open(
      url,
      "ldc-presenter-overlay",
      "popup=yes,width=420,height=740,menubar=no,toolbar=no,location=no,status=no",
    );
    if (!win) {
      setErrorContext("overlay");
      setError("Pop-up blocked. Allow pop-ups, then open the presenter overlay again.");
    }
  }

  const mockMode = session?.mock_mode;
  const stateGuide = (() => {
    if (!session) return emptyLiveDemoGuide();
    if (session.declined) return declinedLiveDemoGuide();
    if (status?.needs_host_action) return waitingHostGuide(status.hint);
    if (botJoined) return liveJoinedGuide(Boolean(mockMode));
    if (session.disclosure_accepted) return consentReadyGuide();
    return meetingCreatedGuide();
  })();

  const stateGuideTone = (() => {
    if (session?.declined) return "danger" as const;
    if (status?.needs_host_action) return "warning" as const;
    if (botJoined) return "success" as const;
    if (session?.disclosure_accepted) return "accent" as const;
    if (session) return "neutral" as const;
    return "accent" as const;
  })();

  return (
    <div
      className="live-demo-operate flex flex-col gap-4 p-6"
      data-testid="live-demo-copilot-page"
    >
      <PageHeader title={PAGE_TITLE} description={PAGE_DESCRIPTION} />

      <LiveDemoStageRail step={step} />

      <LiveDemoStateGuide
        tone="warning"
        testId="live-demo-honesty"
        guide={liveDemoHonestyGuide(mockMode)}
      />

      <div className="ldc-limits" data-testid="live-demo-limits">
        <h2 className="ldc-limits-title">What this session can do</h2>
        <p className="ldc-limits-body">
          A visible, named meeting bot joins Zoom, Meet or Teams (never WhatsApp). It picks out the
          client&apos;s Odoo questions and gives you 2–3 short private answers. Nothing is kept after the
          meeting unless you choose to. Keep the answer panel off any shared screen.
        </p>
      </div>

      {error ? (
        <LiveDemoErrorNotice
          message={error}
          context={errorContext}
          onDismiss={() => setError(null)}
          onRetry={
            errorContext === "disclosure"
              ? () => {
                  setError(null);
                  api
                    .liveDemoCopilotDisclosure()
                    .then(setDisclosure)
                    .catch((err: Error) => {
                      setErrorContext("disclosure");
                      setError(err.message);
                    });
                }
              : errorContext === "status" && session
                ? () => void onRefreshStatus()
                : errorContext === "leave" && session
                  ? () => void onRetryLeavePurge()
                  : undefined
          }
        />
      ) : null}

      <LiveDemoStateGuide
        tone={stateGuideTone}
        testId="live-demo-state-guide"
        guide={stateGuide}
        live={Boolean(session?.declined || status?.needs_host_action)}
      />

      <section className="ldc-panel space-y-4" data-testid="live-demo-meeting-panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="ldc-panel-title">1. Meeting</h2>
            <p className="ldc-panel-sub">
              Paste the meeting link and the display name(s) Stage 1 should ignore.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {session ? (
              <span data-testid="live-demo-mode-badge">
                <Badge variant={mockMode ? "warning" : "info"}>
                  {modeBadgeLabel(mockMode)}
                </Badge>
              </span>
            ) : null}
            {session && status ? (
              <span data-testid="live-demo-status-badge">
                <Badge variant={statusBadgeVariant(status.severity)}>
                  {sanitizeLiveDemoCopy(status.label)}
                </Badge>
              </span>
            ) : null}
          </div>
        </div>
        <form className="space-y-3" onSubmit={onCreate}>
          <label className="ldc-field">
            <span>Meeting URL (Zoom / Google Meet / Teams)</span>
            <Input
              value={meetingUrl}
              onChange={(e) => setMeetingUrl(e.target.value)}
              placeholder="https://zoom.us/j/..."
              required
              data-testid="live-demo-meeting-url"
            />
          </label>
          <label className="ldc-field">
            <span>Bot display name</span>
            <Input
              value={botName}
              onChange={(e) => setBotName(e.target.value)}
              data-testid="live-demo-bot-name"
            />
          </label>
          <label className="ldc-field">
            <span>Your meeting display name(s) - ignored for Stage 1/2 (comma-separated)</span>
            <Input
              value={presenterNames}
              onChange={(e) => setPresenterNames(e.target.value)}
              placeholder="e.g. Fabian Umole, Fabian"
              data-testid="live-demo-presenter-names"
            />
          </label>
          <div className="ldc-actions">
            <Button
              type="submit"
              variant="secondary"
              disabled={busy || !meetingUrl.trim()}
              data-testid="live-demo-create-btn"
            >
              Create session
            </Button>
          </div>
        </form>
      </section>

      {disclosure ? (
        <section className="ldc-panel space-y-4" data-testid="live-demo-consent-panel">
          <div>
            <h2 className="ldc-panel-title">2. {sanitizeLiveDemoCopy(disclosure.title)}</h2>
            <p className="ldc-panel-sub">{sanitizeLiveDemoCopy(disclosure.summary)}</p>
          </div>
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-ink/85">
            {disclosure.bullets.map((b) => (
              <li key={b}>{sanitizeLiveDemoCopy(b)}</li>
            ))}
          </ul>
          <p className="text-sm text-muted">{sanitizeLiveDemoCopy(disclosure.opt_out)}</p>
          {disclosure.delivery?.length ? (
            <div data-testid="live-demo-delivery">
              <p className="text-sm font-medium text-ink">Where answers go</p>
              <ul className="mt-1 space-y-1 text-sm">
                {disclosure.delivery.map((d) => (
                  <li key={d.id} data-testid={`live-demo-delivery-${d.id}`} className={d.available ? "text-ink" : "text-muted"}>
                    {d.label}
                    {" \u00b7 "}
                    {!d.available ? "not available with this meeting bot yet" : d.default ? "on" : "off unless you turn it on for this meeting"}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="ldc-consent-box">
            <label>
              <input
                type="checkbox"
                checked={accepted}
                onChange={(e) => setAccepted(e.target.checked)}
                data-testid="live-demo-accept-disclosure"
              />
              <span>I accept this disclosure (version {disclosure.version}).</span>
            </label>
            <label>
              <input
                type="checkbox"
                checked={notified}
                onChange={(e) => setNotified(e.target.checked)}
                data-testid="live-demo-notify-attendees"
              />
              <span>I will notify / have notified all attendees before the bot joins.</span>
            </label>
            <label>
              <input
                type="checkbox"
                checked={retentionOptIn}
                onChange={(e) => setRetentionOptIn(e.target.checked)}
                data-testid="live-demo-retention-opt-in"
              />
              <span>
                Optional: retain session data after the meeting to improve the knowledge base
                (default is do not retain).
              </span>
            </label>
          </div>
          <div className="ldc-actions">
            <Button
              variant="secondary"
              disabled={busy || !session || !accepted || !notified || Boolean(session?.declined)}
              onClick={() => void onConsent(true)}
              data-testid="live-demo-record-consent"
            >
              Record consent
            </Button>
            <Button
              variant="ghost"
              disabled={busy || !session || Boolean(session?.declined)}
              onClick={() => void onConsent(false)}
              data-testid="live-demo-decline"
            >
              Decline
            </Button>
          </div>
        </section>
      ) : null}

      <section className="ldc-panel space-y-4" data-testid="live-demo-bot-panel">
        <div>
          <h2 className="ldc-panel-title">3. Bot control</h2>
          <p className="ldc-panel-sub">
            {PRIMARY_CTA} is the only teal primary. Launch stays blocked until consent is recorded.
            Without Attendee keys, set{" "}
            <code className="rounded bg-surface-muted px-1">ATTENDEE_ALLOW_MOCK=true</code> for UI
            testing (disabled when{" "}
            <code className="rounded bg-surface-muted px-1">APP_ENVIRONMENT=production</code>).
          </p>
        </div>

        {session && status ? (
          <Callout
            variant={calloutVariant(status.severity)}
            title={sanitizeLiveDemoCopy(status.label)}
            testId="live-demo-bot-status"
          >
            <p>{sanitizeLiveDemoCopy(status.hint)}</p>
            {status.needs_host_action ? (
              <p className="mt-2 font-medium text-ink">
                Host action needed in the meeting (admit bot / grant recording).
              </p>
            ) : null}
            {session.leave_purge_status === "pending" ? (
              <p className="mt-2">Leave/purge job running in the background...</p>
            ) : null}
            {session.leave_purge_status === "failed" && session.last_ops_error ? (
              <p className="mt-2">
                Leave/purge failed: {sanitizeLiveDemoCopy(session.last_ops_error)}
              </p>
            ) : null}
          </Callout>
        ) : null}

        <div className="ldc-actions">
          <Button
            variant="primary"
            disabled={busy || !canLaunch}
            onClick={() => void onLaunch()}
            data-testid="live-demo-launch-btn"
          >
            {busy && canLaunch ? "Launching..." : PRIMARY_CTA}
          </Button>
          <Button
            variant="ghost"
            disabled={busy || !session?.attendee_bot_id}
            onClick={() => void onRefreshStatus()}
            data-testid="live-demo-refresh-btn"
          >
            Refresh status
          </Button>
          <Button
            variant="ghost"
            disabled={busy || !session?.attendee_bot_id}
            onClick={() => void onLeave()}
            data-testid="live-demo-leave-btn"
          >
            Leave &amp; end
          </Button>
          {session?.leave_purge_status === "failed" ? (
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => void onRetryLeavePurge()}
              data-testid="live-demo-retry-purge-btn"
            >
              Retry leave/purge
            </Button>
          ) : null}
        </div>
        {session?.attendee_bot_id ? (
          <p className="ldc-mono" data-testid="live-demo-bot-id">
            Bot id: {session.attendee_bot_id}
          </p>
        ) : null}
      </section>

      <section className="ldc-panel space-y-4" data-testid="live-demo-overlay-panel">
        <div>
          <h2 className="ldc-panel-title">4. Presenter overlay</h2>
          <p className="ldc-panel-sub">
            Pop out a private HUD for live bullets. Share the meeting app or Odoo tab only. Keep this
            overlay on another monitor (or outside the shared window). Clients must never see it.
          </p>
        </div>
        <div className="ldc-actions">
          <Button
            variant="secondary"
            disabled={!session?.id}
            onClick={() => openPresenterOverlay()}
            data-testid="open-presenter-overlay"
          >
            Open presenter overlay
          </Button>
          <Button
            variant="ghost"
            disabled={busy || !session?.id}
            onClick={() => void savePresenterNames()}
            data-testid="save-presenter-speakers"
          >
            Save presenter names
          </Button>
        </div>
        {session ? (
          <p className="text-xs text-muted" data-testid="live-demo-ignore-speakers">
            Ignoring speakers:{" "}
            {(session.presenter_speakers || []).length
              ? session.presenter_speakers.join(", ")
              : "none set (bot still ignored)"}
          </p>
        ) : null}
      </section>

      <section className="ldc-panel space-y-4" data-testid="live-demo-answers-panel">
        <div>
          <h2 className="ldc-panel-title">5. Live answers (Stage 1 to 2)</h2>
          <p className="ldc-panel-sub">
            Odoo-relevant client questions trigger Expert RAG, compressed to 2-3 bullets. Low-confidence
            answers still surface with a clear flag (never silent mid-demo).
          </p>
        </div>
        <div className="space-y-3" data-testid="live-demo-answers-feed">
          {!feedHydrated ? (
            <div className="space-y-2" data-testid="live-demo-answers-loading">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : answers.length === 0 ? (
            <LiveDemoStateGuide
              tone="neutral"
              testId="live-demo-answers-empty"
              guide={emptyAnswersGuide(canLaunch, Boolean(mockMode))}
              actions={
                mockMode ? (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={busy || !mockText.trim() || !session?.id}
                    onClick={() => void onMockUtterance()}
                  >
                    Inject mock line
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={!session?.id || busy}
                    onClick={() => void onRefreshStatus()}
                  >
                    Refresh bot status
                  </Button>
                )
              }
            />
          ) : (
            answers.map((a) => (
              <div key={a.id} className="ldc-answer" data-testid="live-demo-answer-card">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge variant={a.confidence === "high" ? "success" : "warning"}>
                    {a.confidence} confidence
                  </Badge>
                  <Badge variant="default">{a.status}</Badge>
                </div>
                <p className="text-sm text-muted">
                  <span className="font-medium text-accent">{a.speaker_name || "Client"}</span>
                  {" - "}
                  {sanitizeLiveDemoCopy(a.question)}
                </p>
                {a.confidence_flag ? (
                  <p className="mt-2 text-sm font-medium text-warning-strong">
                    {sanitizeLiveDemoCopy(a.confidence_flag)}
                  </p>
                ) : null}
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink">
                  {a.bullets.map((b) => (
                    <li key={b}>{sanitizeLiveDemoCopy(b)}</li>
                  ))}
                </ul>
                {session?.id && a.status !== "pending" ? (
                  <button
                    type="button"
                    className="ldc-fresh"
                    data-testid="live-demo-fresh-answer"
                    disabled={freshId === a.id}
                    onClick={() => void freshAnswer(session.id, a.id)}
                  >
                    {freshId === a.id ? "Getting a fresh answer…" : "Fresh answer"}
                  </button>
                ) : null}
              </div>
            ))
          )}
        </div>
      </section>

      <section className="ldc-panel space-y-4" data-testid="live-demo-transcript-panel">
        <div>
          <h2 className="ldc-panel-title">6. Live transcript</h2>
          <p className="ldc-panel-sub">
            Speaker-tagged lines from Attendee{" "}
            <code className="rounded bg-surface-muted px-1">transcript.update</code> webhooks (or mock
            utterances). Triggered Odoo questions appear in section 5 and the presenter overlay.
          </p>
        </div>
        {session?.mock_mode ? (
          <div className="flex flex-wrap items-end gap-2">
            <label className="ldc-field min-w-[16rem] flex-1">
              <span>Mock client utterance</span>
              <Input
                value={mockText}
                onChange={(e) => setMockText(e.target.value)}
                data-testid="live-demo-mock-text"
              />
            </label>
            <Button
              variant="secondary"
              disabled={busy || !mockText.trim()}
              onClick={() => void onMockUtterance()}
              data-testid="live-demo-inject-btn"
            >
              Inject line
            </Button>
          </div>
        ) : null}
        <div className="ldc-feed" data-testid="live-demo-transcript-feed">
          {!feedHydrated ? (
            <div className="space-y-2" data-testid="live-demo-transcript-loading">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : lines.length === 0 ? (
            <LiveDemoStateGuide
              tone="neutral"
              testId="live-demo-transcript-empty"
              guide={emptyTranscriptGuide(canLaunch, Boolean(mockMode))}
              actions={
                session?.mock_mode ? (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={busy || !mockText.trim() || !session?.id}
                    onClick={() => void onMockUtterance()}
                  >
                    Inject mock line
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={!canLaunch || busy}
                    onClick={() => void onLaunch()}
                  >
                    {PRIMARY_CTA}
                  </Button>
                )
              }
            />
          ) : (
            <ul className="space-y-2">
              {lines.map((line, i) => (
                <li key={`${line.timestamp_ms ?? i}-${i}`} className="text-sm">
                  <span className="font-medium text-accent">{line.speaker_name}</span>
                  <span className="text-ink"> - {sanitizeLiveDemoCopy(line.text)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
      {session && ["ended", "data_deleted", "post_processing"].includes(String(session.bot_state)) ? (
        <AfterMeetingPanel sessionId={session.id} />
      ) : null}
    </div>
  );
}
