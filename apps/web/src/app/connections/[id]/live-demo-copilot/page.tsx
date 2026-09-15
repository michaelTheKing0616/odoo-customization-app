"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { Badge } from "@/components/ui/Badge";
import {
  api,
  getApiBase,
  type LiveDemoCopilotDisclosure,
  type LiveDemoAnswer,
  type LiveDemoCopilotSession,
  type LiveDemoTranscriptLine,
} from "@/lib/api";

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

  useEffect(() => {
    api
      .liveDemoCopilotDisclosure()
      .then(setDisclosure)
      .catch((err: Error) => setError(err.message));
  }, []);

  const refreshTranscript = useCallback(async (sid: string) => {
    const tr = await api.liveDemoCopilotTranscript(sid);
    setLines(tr.lines);
  }, []);

  const refreshAnswers = useCallback(async (sid: string) => {
    const res = await api.liveDemoCopilotAnswers(sid);
    setAnswers(res.answers);
  }, []);

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

  const status = session?.bot_status;

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
        setError("Session declined — no bot will join and no audio will be processed.");
      }
    } catch (err) {
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
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onRefreshStatus() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.liveDemoCopilotRefreshStatus(session.id);
      setSession(next);
    } catch (err) {
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
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function openPresenterOverlay() {
    if (!session?.id) return;
    const url = `/live-demo-copilot/overlay?session=${encodeURIComponent(session.id)}&connection=${encodeURIComponent(connectionId)}`;
    window.open(
      url,
      "ldc-presenter-overlay",
      "popup=yes,width=420,height=740,menubar=no,toolbar=no,location=no,status=no",
    );
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <PageHeader
        title="Live Demo Co-Pilot"
        description="Consent-first meeting assist — Attendee bot joins Zoom, Meet, or Teams; answers stay private to you."
      />

      <Callout variant="info" title="Consent · Attendee · Stage 1/2 · Overlay">
        Capture uses self-hosted Attendee (visible bot). Stage 1→2 answers feed the private presenter
        overlay — open it on a second display and never share that window. WhatsApp is permanently out of scope.
      </Callout>

      {error ? <ErrorNotice message={error} /> : null}

      <Card className="space-y-4 p-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-ink">1. Meeting</h2>
          {session && status ? (
            <Badge variant={statusBadgeVariant(status.severity)}>
              {status.label}
              {session.mock_mode ? " · mock" : ""}
            </Badge>
          ) : null}
        </div>
        <form className="space-y-3" onSubmit={onCreate}>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Meeting URL (Zoom / Google Meet / Teams)</span>
            <Input
              value={meetingUrl}
              onChange={(e) => setMeetingUrl(e.target.value)}
              placeholder="https://zoom.us/j/…"
              required
            />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">Bot display name</span>
            <Input value={botName} onChange={(e) => setBotName(e.target.value)} />
          </label>
          <label className="block space-y-1.5 text-sm">
            <span className="text-muted">
              Your meeting display name(s) — ignored for Stage 1/2 (comma-separated)
            </span>
            <Input
              value={presenterNames}
              onChange={(e) => setPresenterNames(e.target.value)}
              placeholder="e.g. Fabian Umole, Fabian"
            />
          </label>
          <Button type="submit" disabled={busy || !meetingUrl.trim()}>
            Create session
          </Button>
        </form>
      </Card>

      {disclosure ? (
        <Card className="space-y-4 p-5">
          <h2 className="text-base font-semibold text-ink">2. {disclosure.title}</h2>
          <p className="text-sm text-ink/90">{disclosure.summary}</p>
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-ink/85">
            {disclosure.bullets.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
          <p className="text-sm text-muted">{disclosure.opt_out}</p>
          <div className="space-y-2 rounded-lg border border-border-subtle bg-surface-raised/60 p-4">
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={accepted}
                onChange={(e) => setAccepted(e.target.checked)}
              />
              <span>I accept this disclosure (version {disclosure.version}).</span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={notified}
                onChange={(e) => setNotified(e.target.checked)}
              />
              <span>I will notify / have notified all attendees before the bot joins.</span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={retentionOptIn}
                onChange={(e) => setRetentionOptIn(e.target.checked)}
              />
              <span>
                Optional: retain session data after the meeting to improve the knowledge base
                (default is do not retain).
              </span>
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              disabled={busy || !session || !accepted || !notified}
              onClick={() => void onConsent(true)}
            >
              Record consent
            </Button>
            <Button variant="ghost" disabled={busy || !session} onClick={() => void onConsent(false)}>
              Decline
            </Button>
          </div>
        </Card>
      ) : null}

      <Card className="space-y-4 p-5">
        <h2 className="text-base font-semibold text-ink">3. Bot control</h2>
        <p className="text-sm text-muted">
          Launch is blocked until consent is recorded. Without Attendee keys, set{" "}
          <code className="rounded bg-surface-raised px-1">ATTENDEE_ALLOW_MOCK=true</code> for UI
          testing (disabled when <code className="rounded bg-surface-raised px-1">APP_ENVIRONMENT=production</code>).
        </p>

        {session && status ? (
          <Callout
            variant={calloutVariant(status.severity)}
            title={status.label}
          >
            <p>{status.hint}</p>
            {status.needs_host_action ? (
              <p className="mt-2 font-medium text-ink">
                Host action needed in the meeting (admit bot / grant recording).
              </p>
            ) : null}
            {session.leave_purge_status === "pending" ? (
              <p className="mt-2">Leave/purge job running in the background…</p>
            ) : null}
            {session.leave_purge_status === "failed" && session.last_ops_error ? (
              <p className="mt-2">Leave/purge failed: {session.last_ops_error}</p>
            ) : null}
          </Callout>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button disabled={busy || !canLaunch} onClick={() => void onLaunch()}>
            Launch bot
          </Button>
          <Button
            variant="ghost"
            disabled={busy || !session?.attendee_bot_id}
            onClick={() => void onRefreshStatus()}
          >
            Refresh status
          </Button>
          <Button
            variant="ghost"
            disabled={busy || !session?.attendee_bot_id}
            onClick={() => void onLeave()}
          >
            Leave &amp; end
          </Button>
          {session?.leave_purge_status === "failed" ? (
            <Button variant="secondary" disabled={busy} onClick={() => void onRetryLeavePurge()}>
              Retry leave/purge
            </Button>
          ) : null}
        </div>
        {session?.attendee_bot_id ? (
          <p className="text-xs text-muted">Bot id: {session.attendee_bot_id}</p>
        ) : null}
      </Card>

      <Card className="space-y-4 p-5">
        <h2 className="text-base font-semibold text-ink">4. Presenter overlay</h2>
        <p className="text-sm text-muted">
          Pop out a private HUD for live bullets. Share the meeting app or Odoo tab only — keep this
          overlay on another monitor (or outside the shared window). Clients must never see it.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="primary"
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
          <p className="text-xs text-muted">
            Ignoring speakers:{" "}
            {(session.presenter_speakers || []).length
              ? session.presenter_speakers.join(", ")
              : "none set (bot still ignored)"}
          </p>
        ) : null}
      </Card>

      <Card className="space-y-4 p-5">
        <h2 className="text-base font-semibold text-ink">5. Live answers (Stage 1 → 2)</h2>
        <p className="text-sm text-muted">
          Odoo-relevant client questions trigger Expert RAG, compressed to 2–3 bullets. Low-confidence
          answers still surface with a clear flag (never silent mid-demo).
        </p>
        <div className="space-y-3">
          {answers.length === 0 ? (
            <p className="text-sm text-muted">No triggered answers yet.</p>
          ) : (
            answers.map((a) => (
              <div
                key={a.id}
                className="rounded-lg border border-border-subtle bg-surface-raised/50 p-4"
              >
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge variant={a.confidence === "high" ? "success" : "warning"}>
                    {a.confidence} confidence
                  </Badge>
                  <Badge variant="default">{a.status}</Badge>
                </div>
                <p className="text-sm text-muted">
                  <span className="font-medium text-accent">{a.speaker_name || "Client"}</span>
                  {" — "}
                  {a.question}
                </p>
                {a.confidence_flag ? (
                  <p className="mt-2 text-sm font-medium text-warning-strong">{a.confidence_flag}</p>
                ) : null}
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink">
                  {a.bullets.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </div>
      </Card>

      <Card className="space-y-4 p-5">
        <h2 className="text-base font-semibold text-ink">6. Live transcript</h2>
        <p className="text-sm text-muted">
          Speaker-tagged lines from Attendee{" "}
          <code className="rounded bg-surface-raised px-1">transcript.update</code> webhooks (or mock
          utterances). Triggered Odoo questions appear in section 5 and the presenter overlay.
        </p>
        {session?.mock_mode ? (
          <div className="flex flex-wrap items-end gap-2">
            <label className="min-w-[16rem] flex-1 space-y-1.5 text-sm">
              <span className="text-muted">Mock client utterance</span>
              <Input value={mockText} onChange={(e) => setMockText(e.target.value)} />
            </label>
            <Button disabled={busy || !mockText.trim()} onClick={() => void onMockUtterance()}>
              Inject line
            </Button>
          </div>
        ) : null}
        <div className="max-h-80 overflow-y-auto rounded-lg border border-border-subtle bg-surface p-3">
          {lines.length === 0 ? (
            <p className="text-sm text-muted">No transcript yet.</p>
          ) : (
            <ul className="space-y-2">
              {lines.map((line, i) => (
                <li key={`${line.timestamp_ms ?? i}-${i}`} className="text-sm">
                  <span className="font-medium text-accent">{line.speaker_name}</span>
                  <span className="text-ink"> — {line.text}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </div>
  );
}
