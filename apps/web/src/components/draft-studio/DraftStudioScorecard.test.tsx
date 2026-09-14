/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DraftStudioScorecard } from "./DraftStudioScorecard";

afterEach(() => cleanup());

const noop = vi.fn();

describe("DraftStudioScorecard", () => {
  it("keeps Completeness / Cert / Autopilot as three bars", () => {
    render(
      <DraftStudioScorecard
        scorecard={{
          score_0_10: 7.2,
          validators: { all_green: true },
          dimensions: { domain_fit: 7, structure: 7, semantics: 7, ux: 7, hygiene: 8 },
        }}
        certification={{ tier: "ReviewRequired", quality: 70, evidence: 40, risk: 20 }}
        certTierDisplay="ReviewRequired"
        certShipReady={false}
        goLiveReady={false}
        stockReuse={false}
        isComponent={false}
        refuseClone={false}
        aiBusy={false}
        hasDraft
        expertHint="Expert closer repairs this JSON hygiene."
        eliteBusy={false}
        eliteLintOk={null}
        eliteLintNote={null}
        eliteValidationId={null}
        eliteZipBase64={null}
        eliteNote={null}
        expertReviewNote={null}
        expertReviewFindings={[]}
        finisherComplete
        onExpertFix={noop}
        onLint={noop}
        onValidate={noop}
        onPromote={noop}
        onDownloadValidatedZip={noop}
        onAskExpert={noop}
      />,
    );
    expect(screen.getByTestId("draft-scorecard-chip").textContent).toMatch(
      /Completeness: 7.2\/10/,
    );
    expect(screen.getByTestId("score-bars-legend").textContent).toMatch(
      /Completeness is ModuleSpec hygiene/,
    );
    expect(screen.getByTestId("score-bars-legend").textContent).toMatch(
      /Certification is the ship bar/,
    );
    expect(screen.getByTestId("score-bars-legend").textContent).toMatch(/Autopilot done-bar/);
    expect(screen.getByTestId("expert-review-fix")).toBeTruthy();
    expect(screen.getByTestId("expert-review-fix-hint").textContent).toMatch(/JSON hygiene/);
  });
});
