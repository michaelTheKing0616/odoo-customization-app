"use client";

import { DraftStudioScorecard } from "@/components/draft-studio/DraftStudioScorecard";
import { DraftStudioShell } from "@/components/draft-studio/DraftStudioShell";
import { Callout } from "@/components/ui/Callout";
import { draftStudioJourneyFromState } from "@/lib/draft-studio-journey";
import "@/styles/studio-refinement.css";

export default function DraftStudioE2ePage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const journey = draftStudioJourneyFromState({ hasDraft: true });

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <DraftStudioShell
      connectionId="e2e-mock"
      connectionName="E2E mock"
      journey={journey}
      hasDraft
      onStartNew={() => undefined}
    >
      <Callout variant="info" title="Three independent bars">
        Completeness 8.5/10 is ModuleSpec hygiene, not go-live. Certification is the ship bar.
        Autopilot is RPC smoke on Job Autopilot. Promote stays human.
      </Callout>
      <DraftStudioScorecard
        scorecard={{
          score_0_10: 8.5,
          dimensions: { models: 8, views: 7, automations: 6, security: 9 },
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
          note: "completeness 10.0 is not go-live until Cert ≥ Production",
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
    </DraftStudioShell>
  );
}
