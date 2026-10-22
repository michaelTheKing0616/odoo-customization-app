"use client";

import { useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { DraftStudioApplyBar } from "@/components/draft-studio/DraftStudioApplyBar";
import { DraftStudioProgress } from "@/components/draft-studio/DraftStudioProgress";
import { DraftStudioScorecard } from "@/components/draft-studio/DraftStudioScorecard";
import { DraftStudioShell } from "@/components/draft-studio/DraftStudioShell";
import { Callout } from "@/components/ui/Callout";
import { Textarea } from "@/components/ui/Textarea";
import { draftStudioJourneyFromState } from "@/lib/draft-studio-journey";
import "@/styles/studio-refinement.css";

export default function DraftStudioE2ePage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const params = useSearchParams();
  const mode = params?.get("mode");
  const journey = useMemo(() => draftStudioJourneyFromState({ hasDraft: true }), []);

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  if (mode === "progress") {
    return (
      <DraftStudioShell
        connectionId="e2e-mock"
        connectionName="E2E mock"
        journey={draftStudioJourneyFromState({ generating: true })}
      >
        <DraftStudioProgress label="Enriching ModuleSpec hygiene" />
      </DraftStudioShell>
    );
  }

  if (mode === "brief") {
    return (
      <DraftStudioShell
        connectionId="e2e-mock"
        connectionName="E2E mock"
        journey={draftStudioJourneyFromState({})}
      >
        <section
          className="draft-studio-brief"
          data-testid="draft-studio-brief"
          aria-labelledby="draft-studio-brief-title"
        >
          <h2 id="draft-studio-brief-title" className="draft-studio-brief-title">
            What should we implement?
          </h2>
          <p className="draft-studio-brief-subtitle" id="draft-studio-brief-help">
            A field on a stock form, a feature under an existing app, or a full residual
            workspace. Nothing writes to Odoo until you Apply.
          </p>
          <div className="studio-prompt-composer draft-studio-composer">
            <label htmlFor="draft-nl-prompt" className="sr-only">
              Describe what to implement
            </label>
            <Textarea
              id="draft-nl-prompt"
              className="resize-none text-left studio-prompt-textarea"
              data-testid="draft-nl-prompt"
              defaultValue=""
              rows={4}
              aria-describedby="draft-studio-brief-help draft-studio-brief-status"
              placeholder="Add an SLA due date on invoices, or a law-firm practice with matters, time, and stock quotations."
            />
            <div className="studio-prompt-actions">
              <p className="studio-prompt-shortcut" id="draft-studio-brief-status">
                A sentence or two is enough to start.
              </p>
            </div>
          </div>
          <div className="draft-studio-action-dock mt-4">
            <p className="draft-studio-action-dock-label">Next step</p>
            <DraftStudioApplyBar
              canDraft={false}
              canApply={false}
              hasDraft={false}
              aiBusy={false}
              busy={false}
              zipBusy={false}
              finisherComplete={false}
              refuseClone={false}
              stockReuse={false}
              moduleDelivery={false}
              zipLocked={false}
              generateUiBlocked={null}
              overlapPending={false}
              needsConnectReview={false}
              connectApproved={false}
              designerHref="/e2e"
              designerModel={null}
              jobAutopilotHref="/e2e"
              applied={false}
              onCreateDraft={() => undefined}
              onApply={() => undefined}
              onDownloadZip={() => undefined}
              onOpenModuleSpec={() => undefined}
              onStashJobBrief={() => undefined}
            />
          </div>
        </section>
      </DraftStudioShell>
    );
  }

  return (
    <DraftStudioShell
      connectionId="e2e-mock"
      connectionName="E2E mock"
      journey={journey}
      hasDraft
      onStartNew={() => undefined}
    >
      <Callout variant="info" title="Three independent bars" className="draft-studio-info-soft">
        Completeness is ModuleSpec hygiene, not go-live. Certification is the ship bar.
        Autopilot is RPC smoke on Job Autopilot. Completeness ≠ Cert ≠ Autopilot. Promote stays human.
      </Callout>
      <DraftStudioScorecard
        scorecard={{
          score_0_10: 8.5,
          dimensions: { domain_fit: 8, structure: 7, semantics: 6, ux: 9, hygiene: 8 },
          validators: { all_green: true, xml_ok: true, consistency_ok: true },
          findings: [],
        }}
        certification={{
          tier: "Sandbox",
          quality: 7,
          evidence: 6,
          risk: 3,
          hard_failures: [],
          option_a_pending: true,
          note: "completeness 10 is not go-live until Cert ≥ Production",
        }}
        certTierDisplay="Sandbox"
        certShipReady={false}
        doneBar={{ mode: "review", next_step: "sandbox", go_live_ready: false }}
        goLiveReady={false}
        stockReuse={false}
        isComponent={false}
        refuseClone={false}
        aiBusy={false}
        hasDraft
        expertHint="Expert closer repairs JSON hygiene. It does not auto-promote."
        eliteBusy={false}
        eliteLintOk={null}
        eliteLintNote={null}
        eliteValidationId={null}
        eliteZipBase64={null}
        eliteNote={null}
        expertReviewNote={null}
        expertReviewFindings={[]}
        finisherComplete={false}
        draftSummary="Visitor log · 1 model · 3 fields"
        onExpertFix={() => undefined}
        onLint={() => undefined}
        onValidate={() => undefined}
        onPromote={() => undefined}
        onDownloadValidatedZip={() => undefined}
        onAskExpert={() => undefined}
      />
      <div className="draft-studio-action-dock mt-4">
        <p className="draft-studio-action-dock-label">Next step</p>
        <DraftStudioApplyBar
          canDraft
          canApply
          hasDraft
          aiBusy={false}
          busy={false}
          zipBusy={false}
          finisherComplete
          refuseClone={false}
          stockReuse={false}
          moduleDelivery={false}
          zipLocked={false}
          generateUiBlocked={null}
          overlapPending={false}
          needsConnectReview={false}
          connectApproved
          designerHref="/e2e"
          designerModel="x_visitor_log"
          jobAutopilotHref="/e2e"
          applied={false}
          onCreateDraft={() => undefined}
          onApply={() => undefined}
          onDownloadZip={() => undefined}
          onOpenModuleSpec={() => undefined}
          onStashJobBrief={() => undefined}
        />
      </div>
    </DraftStudioShell>
  );
}
