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
      /Completeness is app plan hygiene/,
    );
    expect(screen.getByTestId("score-bars-legend").textContent).toMatch(
      /Certification is the ship bar/,
    );
    expect(screen.getByTestId("score-bars-legend").textContent).toMatch(/Autopilot done-bar/);
    expect(screen.getByTestId("expert-review-fix")).toBeTruthy();
    expect(screen.getByTestId("expert-review-fix-hint").textContent).toMatch(/JSON hygiene/);
  });
});

describe("DraftStudioScorecard labels and Online honesty", () => {
  const props = {
    scorecard: {
      score_0_10: 9.2,
      validators: { all_green: true },
      dimensions: { domain_fit: 9, structure: 9, semantics: 9, ux: 9, hygiene: 10 },
    },
    certification: { tier: "Sandbox", quality: 80, evidence: 60, risk: 10 },
    certTierDisplay: "Sandbox",
    certShipReady: false,
    goLiveReady: false,
    stockReuse: false,
    isComponent: false,
    refuseClone: false,
    aiBusy: false,
    hasDraft: true,
    expertHint: "",
    eliteBusy: false,
    eliteLintOk: null,
    eliteLintNote: null,
    eliteValidationId: "v1",
    eliteZipBase64: "UEsDBA==",
    eliteNote: null,
    expertReviewNote: null,
    expertReviewFindings: [],
    finisherComplete: true,
    onExpertFix: noop,
    onLint: noop,
    onValidate: noop,
    onPromote: noop,
    onDownloadValidatedZip: noop,
    onAskExpert: noop,
  };

  it("labels Completeness, Certification, and Autopilot as separate tiles", () => {
    render(<DraftStudioScorecard {...props} jobAutopilotHref="/connections/c1/job" />);
    const tiles = screen.getByTestId("score-bars-legend").querySelectorAll(":scope > li");
    expect(tiles).toHaveLength(3);
    expect(tiles[0].textContent).toMatch(/^Completeness/);
    expect(tiles[1].textContent).toMatch(/^Certification/);
    expect(tiles[2].textContent).toMatch(/^Autopilot/);
    // Completeness never borrows the Cert tier and Cert never borrows the score.
    expect(tiles[0].textContent).not.toMatch(/Sandbox/);
    expect(tiles[1].textContent).not.toMatch(/9\.2/);
    expect(tiles[1].textContent).toMatch(/^Certification: Sandbox/);
    expect(screen.getByTestId("certification-chip").textContent).toMatch(/Quality 80/);
  });

  it("keeps Promote available off Online once the module is validated", () => {
    render(<DraftStudioScorecard {...props} />);
    expect(screen.getByTestId("elite-promote-module")).not.toBeDisabled();
    expect(screen.queryByTestId("elite-promote-online-reason")).toBeNull();
  });

  it("disables Promote on Odoo Online and says why", () => {
    render(<DraftStudioScorecard {...props} isOdooOnline />);
    expect(screen.getByTestId("elite-promote-module")).toBeDisabled();
    expect(screen.getByTestId("elite-promote-online-reason").textContent).toMatch(
      /Odoo Online does not allow custom modules/,
    );
  });
});
