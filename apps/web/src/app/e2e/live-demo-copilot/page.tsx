"use client";

import { Suspense } from "react";
import { OperateStudioBar } from "@/components/operate-studio/OperateStudioBar";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/layout-primitives";
import { LiveDemoErrorNotice } from "@/components/live-demo-copilot/LiveDemoErrorNotice";
import { LiveDemoStageRail } from "@/components/live-demo-copilot/LiveDemoStageRail";
import { LiveDemoStateGuide } from "@/components/live-demo-copilot/LiveDemoStateGuide";
import {
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  sanitizeLiveDemoCopy,
  liveDemoSessionBadge,
  PRIMARY_CTA,
  consentReadyGuide,
  declinedLiveDemoGuide,
  emptyAnswersGuide,
  emptyLiveDemoGuide,
  emptyTranscriptGuide,
  liveDemoHonestyGuide,
  liveJoinedGuide,
  meetingCreatedGuide,
  waitingHostGuide,
  type LiveDemoStepIndex,
} from "@/lib/liveDemoCopilotScreen";
import "@/components/live-demo-copilot/live-demo-copilot-operate.css";

const STATES = [
  "empty",
  "consent",
  "ready",
  "mock",
  "live",
  "declined",
  "waiting",
  "answers",
  "error",
] as const;
type HarnessState = (typeof STATES)[number];

function stepFor(state: HarnessState): LiveDemoStepIndex {
  if (state === "empty") return 1;
  if (state === "consent" || state === "declined") return 2;
  if (state === "ready") return 3;
  return 4;
}

function LiveDemoHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "empty";
  const state = (STATES.includes(raw as HarnessState) ? raw : "empty") as HarnessState;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  const mockMode = state === "mock" || state === "answers";
  const canLaunch = state === "ready";
  const honesty = liveDemoHonestyGuide(
    state === "empty" || state === "consent" || state === "error" || state === "declined"
      ? null
      : mockMode
        ? true
        : false,
  );

  const stateGuide =
    state === "empty"
      ? emptyLiveDemoGuide()
      : state === "consent"
        ? meetingCreatedGuide()
        : state === "ready"
          ? consentReadyGuide()
          : state === "declined"
            ? declinedLiveDemoGuide()
            : state === "waiting"
              ? waitingHostGuide("Admit the bot from the Zoom waiting room.")
              : state === "mock" || state === "answers"
                ? liveJoinedGuide(true)
                : liveJoinedGuide(false);

  const tone =
    state === "declined" || state === "error"
      ? ("danger" as const)
      : state === "waiting"
        ? ("warning" as const)
        : state === "live" || state === "answers" || state === "mock"
          ? ("success" as const)
          : state === "ready"
            ? ("accent" as const)
            : ("neutral" as const);

  return (
    <div
      className="live-demo-operate op-studio-shell p-4 sm:p-6"
      data-testid="live-demo-copilot-page"
      data-harness-state={state}
    >

      <header className="op-studio" data-testid="live-demo-studio-chrome">
        <div className="op-titlebar">
          <div className="op-title-block">
            <p className="op-kicker">E2E mock connection</p>
            <h1 className="op-title">{PAGE_TITLE}</h1>
            <p className="op-subtitle">{PAGE_DESCRIPTION}</p>
          </div>
        </div>
        <OperateStudioBar
          testIdPrefix="live-demo"
          badge={liveDemoSessionBadge(stepFor(state))}
          honesty={honesty}
          sanitize={sanitizeLiveDemoCopy}
        />
        <LiveDemoStageRail step={stepFor(state)} />
      </header>

      <div className="op-desk">
        <div className="op-paper space-y-4">

      <div className="ldc-limits" data-testid="live-demo-limits">
        <h2 className="ldc-limits-title">What this session can do</h2>
        <p className="ldc-limits-body">
          Visible Attendee bot only. WhatsApp is permanently out of scope. Stage 1 filters
          Odoo-relevant client questions; Stage 2 compresses Expert RAG to 2-3 private bullets.
          Retention defaults to do not retain. Presenter overlay is never for screen share.
        </p>
      </div>

      {state === "error" ? (
        <LiveDemoErrorNotice message="Attendee timed out while joining" context="launch" />
      ) : null}

      <LiveDemoStateGuide
        tone={tone}
        testId="live-demo-state-guide"
        guide={stateGuide}
        live={state === "declined" || state === "waiting"}
      />

      <section className="ldc-panel space-y-4" data-testid="live-demo-meeting-panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="ldc-panel-title">1. Meeting</h2>
            <p className="ldc-panel-sub">Paste the meeting link and display name(s) to ignore.</p>
          </div>
          {state !== "empty" ? (
            <span data-testid="live-demo-mode-badge">
              <Badge variant={mockMode ? "warning" : "info"}>
                {mockMode ? "Mock" : "Live"}
              </Badge>
            </span>
          ) : null}
        </div>
        <label className="ldc-field">
          <span>Meeting URL (Zoom / Google Meet / Teams)</span>
          <Input
            defaultValue={state === "empty" ? "" : "https://zoom.us/j/123456789"}
            data-testid="live-demo-meeting-url"
            readOnly
          />
        </label>
        <div className="ldc-actions">
          <Button type="button" variant="secondary" data-testid="live-demo-create-btn">
            Create session
          </Button>
        </div>
      </section>

      {state !== "empty" ? (
        <section className="ldc-panel space-y-4" data-testid="live-demo-consent-panel">
          <div>
            <h2 className="ldc-panel-title">2. Recording and transcription disclosure</h2>
            <p className="ldc-panel-sub">
              A visible bot may join and transcribe. Answers stay on your private overlay.
            </p>
          </div>
          <div className="ldc-consent-box">
            <label>
              <input
                type="checkbox"
                defaultChecked={state !== "consent" && state !== "declined"}
                data-testid="live-demo-accept-disclosure"
                readOnly
              />
              <span>I accept this disclosure (version 1).</span>
            </label>
            <label>
              <input
                type="checkbox"
                defaultChecked={state !== "consent" && state !== "declined"}
                data-testid="live-demo-notify-attendees"
                readOnly
              />
              <span>I will notify / have notified all attendees before the bot joins.</span>
            </label>
          </div>
          <div className="ldc-actions">
            <Button
              type="button"
              variant="secondary"
              data-testid="live-demo-record-consent"
              disabled={state === "declined" || state === "ready" || stepFor(state) >= 3}
            >
              Record consent
            </Button>
            <Button type="button" variant="ghost" data-testid="live-demo-decline">
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
          </p>
        </div>
        <div className="ldc-actions">
          <Button
            type="button"
            variant="primary"
            disabled={!canLaunch}
            data-testid="live-demo-launch-btn"
          >
            {PRIMARY_CTA}
          </Button>
          <Button
            type="button"
            variant="ghost"
            disabled={stepFor(state) < 4}
            data-testid="live-demo-refresh-btn"
          >
            Refresh status
          </Button>
          <Button
            type="button"
            variant="ghost"
            disabled={stepFor(state) < 4}
            data-testid="live-demo-leave-btn"
          >
            Leave &amp; end
          </Button>
        </div>
      </section>

      <section className="ldc-panel space-y-4" data-testid="live-demo-overlay-panel">
        <div>
          <h2 className="ldc-panel-title">4. Presenter overlay</h2>
          <p className="ldc-panel-sub">
            Private HUD. Share the meeting or Odoo window only. Never share this overlay.
          </p>
        </div>
        <div className="ldc-actions">
          <Button
            type="button"
            variant="secondary"
            disabled={state === "empty"}
            data-testid="open-presenter-overlay"
          >
            Open presenter overlay
          </Button>
        </div>
      </section>

      <section className="ldc-panel space-y-4" data-testid="live-demo-answers-panel">
        <div>
          <h2 className="ldc-panel-title">5. Live answers (Stage 1 to 2)</h2>
          <p className="ldc-panel-sub">Odoo-relevant questions become 2-3 private bullets.</p>
        </div>
        {state === "answers" ? (
          <div className="ldc-answer" data-testid="live-demo-answer-card">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Badge variant="success">high confidence</Badge>
              <Badge variant="default">ready</Badge>
            </div>
            <p className="text-sm text-muted">
              <span className="font-medium text-accent">Client</span>
              {" - "}
              Can Odoo handle multi-company accounting?
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink">
              <li>Yes with multi-company enabled</li>
              <li>Each company can keep its own chart of accounts</li>
            </ul>
          </div>
        ) : (
          <LiveDemoStateGuide
            tone="neutral"
            testId="live-demo-answers-empty"
            guide={emptyAnswersGuide(canLaunch, mockMode)}
          />
        )}
      </section>

      <section className="ldc-panel space-y-4" data-testid="live-demo-transcript-panel">
        <div>
          <h2 className="ldc-panel-title">6. Live transcript</h2>
          <p className="ldc-panel-sub">Speaker-tagged lines from Attendee or mock utterances.</p>
        </div>
        {state === "answers" || state === "live" || state === "mock" ? (
          <div className="ldc-feed" data-testid="live-demo-transcript-feed">
            <ul className="space-y-2">
              <li className="text-sm">
                <span className="font-medium text-accent">Client</span>
                <span className="text-ink"> - Can Odoo handle multi-company accounting?</span>
              </li>
            </ul>
          </div>
        ) : (
          <div className="ldc-feed" data-testid="live-demo-transcript-feed">
            <LiveDemoStateGuide
              tone="neutral"
              testId="live-demo-transcript-empty"
              guide={emptyTranscriptGuide(canLaunch, mockMode)}
            />
          </div>
        )}
      </section>
        </div>
      </div>

    </div>
  );
}

export default function LiveDemoHarnessPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness...</main>}>
      <LiveDemoHarnessInner />
    </Suspense>
  );
}
