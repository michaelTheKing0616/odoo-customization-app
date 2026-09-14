"use client";

import { StudioBriefScreen } from "@/components/studio/StudioBriefScreen";
import { StudioHonestyBanners } from "@/components/studio/StudioHonestyBanners";
import { StudioShell } from "@/components/studio/StudioShell";
import { studioJourneyFromPhase } from "@/lib/studio-journey";
import "@/styles/studio-refinement.css";

export default function StudioE2ePage() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const journey = studioJourneyFromPhase({ phase: "prompt" });

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <StudioShell connectionId="e2e-mock" journey={journey}>
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
        liveAppName="Visitor log"
        grammarCard={{
          shape: "one_document",
          display_name: "Visitor log",
          header_model: "x_visitor_log",
          document_count: 1,
          slots: ["guest", "host"],
          states: ["draft", "checked_in"],
          extra_apps: 0,
          summary:
            "A Visitor log form with Guest, Host, and Checked in. Nothing is installed until you apply.",
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
      <StudioBriefScreen
        prompt="Front desk signs visitors in and notifies the host."
        busy={false}
        onPromptChange={() => undefined}
        onStart={() => undefined}
      />
    </StudioShell>
  );
}
