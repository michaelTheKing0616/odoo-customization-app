"use client";

import { useEffect, useRef, useState } from "react";
import { ClarifyInterstitial } from "@/components/studio/ClarifyInterstitial";
import { ReviewRefineLayout } from "@/components/studio/ReviewRefineLayout";
import { StudioApplyBar } from "@/components/studio/StudioApplyBar";
import { StudioBriefScreen } from "@/components/studio/StudioBriefScreen";
import { StudioChatThread } from "@/components/studio/StudioChatThread";
import {
  StudioGeneratingCanvas,
  StudioGenerationFailed,
} from "@/components/studio/StudioGenerationStates";
import { StudioHonestyBanners } from "@/components/studio/StudioHonestyBanners";
import { StudioMobileTabs } from "@/components/studio/StudioMobileTabs";
import { StudioPreviewPane } from "@/components/studio/StudioPreviewPane";
import { StudioRefineComposer } from "@/components/studio/StudioRefineComposer";
import { StudioShell } from "@/components/studio/StudioShell";
import type { PreviewFormView } from "@/lib/draft-form-preview";
import {
  CUSTOMER_HEALTH_FORM,
  CUSTOMER_HEALTH_PLAN,
} from "@/components/odoo-preview/fixtures/customer-health";
import { studioJourneyFromPhase } from "@/lib/studio-journey";
import type { StudioClarification, StudioTurn } from "@/lib/studio-session";
import "@/styles/studio-refinement.css";

/**
 * App Studio harness (UI-S-20). `?state=` picks a screen:
 * brief (default) · diagnosis · generating · failed · review.
 * Production components only; no API calls.
 */
type HarnessState = "brief" | "diagnosis" | "generating" | "failed" | "review";

const VISITOR_FORM: PreviewFormView = {
  type: "form",
  model: "x_visitor_log",
  title: "Visitor log",
  statusbar: {
    field: "x_state",
    stages: ["draft", "checked_in", "checked_out"],
    activeStage: "draft",
  },
  headerButtons: [{ id: "check_in", string: "Check in", variant: "primary" }],
  groups: [
    {
      id: "visit",
      string: "Visit",
      columns: 2,
      fields: [
        { id: "x_name", name: "x_name", string: "Guest", ttype: "char", required: true },
        { id: "x_host_id", name: "x_host_id", string: "Host", ttype: "many2one" },
        { id: "x_company", name: "x_company", string: "Company", ttype: "char" },
        { id: "x_checked_in", name: "x_checked_in", string: "Checked in", ttype: "datetime" },
      ],
    },
  ],
  chatter: "stub",
};

const DIAGNOSIS: StudioClarification = {
  kind: "diagnosis",
  merge_key: "diagnosis",
  question: "Does this match?",
  help: "A Visitor log app: front desk signs guests in and the host gets notified.",
  options: [],
  understanding: {
    title: "Visitor log",
    host_model: null,
    inherit_existing: false,
    needs_module: false,
    constraints: ["Notify the host when a guest checks in", "Record check-out time"],
  },
} as StudioClarification;

const TURNS: StudioTurn[] = [
  { role: "user", kind: "refine", content: "Make Host required", at: "2026-10-05T15:10:00Z" },
  {
    role: "assistant",
    kind: "refine_result",
    content: "Host is now required on the Visitor log form.",
    at: "2026-10-05T15:10:04Z",
  },
];

const HEALTH_TURNS: StudioTurn[] = [
  { role: "user", kind: "refine", content: "Make Customer required", at: "2026-10-05T15:10:00Z" },
  {
    role: "assistant",
    kind: "refine_result",
    content: "Customer is now required on the Customer Health form.",
    at: "2026-10-05T15:10:04Z",
  },
];

const HARNESS_COPY = {
  visitor: {
    app: "Visitor log",
    section: "Visitor log",
    model: "x_visitor_log",
    turns: TURNS,
    chips: ["Add a Purpose field", "Make Company optional"],
    slots: ["guest", "host"],
    states: ["draft", "checked_in"],
    summary:
      "A Visitor log form with Guest, Host, and Checked in. Nothing is installed until you apply.",
  },
  health: {
    app: "Customer Health",
    section: "Customer Success",
    model: "x_customer_health",
    turns: HEALTH_TURNS,
    chips: ["Add a Next review date field", "Make Owner optional"],
    slots: ["customer", "owner", "score"],
    states: ["healthy", "watch", "at_risk", "churned"],
    summary:
      "A Customer Health form with Customer, Health score, Risk level, and a Signals list. Nothing is installed until you apply.",
  },
} as const;

function readState(): HarnessState {
  if (typeof window === "undefined") return "brief";
  const raw = new URLSearchParams(window.location.search).get("state");
  return raw === "diagnosis" ||
    raw === "generating" ||
    raw === "failed" ||
    raw === "review"
    ? raw
    : "brief";
}

function readFixture(): "visitor" | "health" {
  if (typeof window === "undefined") return "visitor";
  return new URLSearchParams(window.location.search).get("fixture") === "health" ? "health" : "visitor";
}

export default function StudioE2ePage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const [state, setState] = useState<HarnessState>("brief");
  const [prompt, setPrompt] = useState("Front desk signs visitors in and notifies the host.");
  const [mobileTab, setMobileTab] = useState<"preview" | "chat">("preview");
  const [refine, setRefine] = useState("");
  const composerRef = useRef<HTMLTextAreaElement | null>(null);

  const [fixture, setFixture] = useState<"visitor" | "health">("visitor");

  useEffect(() => {
    setState(readState());
    setFixture(readFixture());
  }, []);
  const harnessForm = fixture === "health" ? CUSTOMER_HEALTH_FORM : VISITOR_FORM;
  const copy = HARNESS_COPY[fixture];

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  const phase =
    state === "diagnosis"
      ? "clarify"
      : state === "generating"
        ? "generating"
        : state === "failed"
          ? "failed"
          : state === "review"
            ? "review"
            : "prompt";
  const journey = studioJourneyFromPhase({ phase });

  const banners = (
    <StudioHonestyBanners
      connectionId="e2e-mock"
      applyNote={null}
      calloutTitle="Preview only"
      odooAppUrl={null}
      artifactConsistent
      appIsLiveOnOdoo={false}
      stockReuse={false}
      refuseClone={false}
      goldOptionA={false}
      authoredOptionA={false}
      fieldPack={false}
      hostFormName="Vendor bills"
      liveAppName={copy.app}
      grammarCard={{
        shape: "one_document",
        display_name: copy.app,
        header_model: copy.model,
        document_count: 1,
        slots: [...copy.slots],
        states: [...copy.states],
        extra_apps: 0,
        summary: copy.summary,
      }}
      surfaceFindings={[]}
      liveApplyBanner={null}
      unfinishedBanner={null}
      operatorSurface={null}
      placementRows={[]}
      slotCatalog={[]}
      stockApps={[]}
      applyBlocked={null}
      refineBusy={false}
      onPlaceField={() => undefined}
    />
  );

  return (
    <StudioShell
      connectionId="e2e-mock"
      journey={journey}
      canvas={state === "review"}
      hasSession={state !== "brief"}
      onStartNew={() => undefined}
    >
      {state === "brief" ? (
        <>
          {banners}
          <StudioBriefScreen
            prompt={prompt}
            busy={false}
            onPromptChange={setPrompt}
            onStart={() => undefined}
            flashAstEnrich={false}
            onFlashAstEnrichChange={() => undefined}
          />
        </>
      ) : null}

      {state === "diagnosis" ? (
        <ClarifyInterstitial clarification={DIAGNOSIS} busy={false} onAnswer={() => undefined} />
      ) : null}

      {state === "generating" ? (
        <StudioGeneratingCanvas runId={null} fallbackLabel={`Drafting the ${copy.app} form`} />
      ) : null}

      {state === "failed" ? (
        <StudioGenerationFailed
          message="The model returned an incomplete draft."
          retrying={false}
          onRetry={() => undefined}
          onStartOver={() => undefined}
        />
      ) : null}

      {state === "review" ? (
        <div className="studio-review" data-testid="studio-harness-review">
          {banners}
          <StudioMobileTabs value={mobileTab} onChange={setMobileTab} />
          <ReviewRefineLayout
            mobileTab={mobileTab}
            header={
              <div className="panel-header">
                <div className="breadcrumb">
                  <span>{copy.section}</span>
                  <span aria-hidden>›</span>
                  <span className="current">{copy.app}</span>
                </div>
              </div>
            }
            preview={
              <StudioPreviewPane
                draft={{ _generation_engine: { form_preview: harnessForm } }}
                preview={harnessForm}
                breadcrumb={harnessForm.title}
                integrationPlan={fixture === "health" ? CUSTOMER_HEALTH_PLAN : null}
              />
            }
            chat={
              <StudioChatThread
                conversation={[...copy.turns]}
                localRefineError={null}
                refineBusy={false}
                onReuse={setRefine}
                onUndo={() => undefined}
              />
            }
            chatInput={
              <StudioRefineComposer
                composerRef={composerRef}
                chips={[...copy.chips]}
                value={refine}
                fieldPack={false}
                hostFormName={copy.app}
                busy={false}
                onChange={setRefine}
                onSubmit={() => undefined}
              />
            }
            footer={
              <StudioApplyBar
                designerHref="/connections/e2e-mock/designer"
                designerModel={copy.model}
                appIsLiveOnOdoo={false}
                fieldPack={false}
                hostFormName={copy.app}
                liveAppName={copy.app}
                goldOptionA={false}
                authoredOptionA={false}
                goldCanOpenSettings={false}
                goldInspect={null}
                openInOdooUrl={null}
                canApply
                stockReuse={false}
                refuseClone={false}
                surfaceBlocked={false}
                applyBlocked={null}
                busy={null}
                onApply={() => undefined}
              />
            }
          />
        </div>
      ) : null}
    </StudioShell>
  );
}
