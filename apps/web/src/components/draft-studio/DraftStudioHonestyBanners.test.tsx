/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DraftStudioHonestyBanners } from "./DraftStudioHonestyBanners";

afterEach(() => cleanup());

const noop = vi.fn();

const base = {
  connectionId: "c1",
  liveApplyBanner: null,
  unfinishedBanner: null,
  generateUiBlocked: null,
  aiNote: null,
  genUiResult: null,
  odooAppUrl: null,
  llmStatusBanner: null as string | null,
  retryDisabled: false,
  showRetry: true,
  aiBusy: false,
  refuseClone: false,
  operatorSurface: null,
  stockReuse: false,
  stockApps: [] as { id: string; label: string }[],
  jobAutopilotHref: "/connections/c1/job",
  draftNeedsRegenerate: false,
  canDraft: true,
  warnings: [] as string[],
  authoredOptionA: false,
  authoringPassed: true,
  hostInstallOffers: [],
  leftoverAuthoringFindings: [],
  isOdooOnline: false,
  optionALines: [] as string[],
  capabilityPrimaryOptionA: false,
  goLiveReady: false,
  zipLocked: false,
  optionAProveBusy: false,
  optionAProveNote: null,
  computeSuggestions: [],
  refusals: [],
  snapshots: [],
  onRetryEnrichment: noop,
  onRegenerate: noop,
  onStashJobBrief: noop,
  onInstallHost: noop,
  onProveOptionA: noop,
  onRestoreSnapshot: noop,
  onLoadWalkthrough: noop,
};

describe("DraftStudioHonestyBanners", () => {
  it("shows wizard live-apply copy and Retry without App Studio surface phrasing", () => {
    render(
      <DraftStudioHonestyBanners
        {...base}
        liveApplyBanner={{
          title: "Not live-apply ready",
          body: "This draft still has live-apply gaps: mixins. Click Expert review and fix, then Apply.",
          testId: "live-apply-not-ready",
        }}
        llmStatusBanner="Draft Studio used the domain pack. Click Retry AI enrichment to tailor when a model is available."
      />,
    );
    expect(screen.getByTestId("live-apply-not-ready").textContent).toMatch(
      /Click Expert review and fix/,
    );
    expect(screen.getByTestId("live-apply-not-ready").textContent).not.toMatch(
      /Repair with Expert/,
    );
    expect(screen.getByTestId("retry-ai-enrichment").textContent).toMatch(/domain pack/);
    expect(screen.getByTestId("retry-ai-enrichment-btn")).toBeTruthy();
  });
});

describe("DraftStudioHonestyBanners clarify and Online honesty", () => {
  const clarify = {
    clarifyQuestion: "Where should inspections live?",
    clarifyOptions: [
      { id: "tasks", label: "On project tasks" },
      { id: "standalone", label: "As a standalone app" },
    ],
    clarifyDefaultId: "tasks",
  };

  it("asks one question with a suggested answer and regenerates on answer", async () => {
    const { fireEvent } = await import("@testing-library/react");
    const onAnswerClarify = vi.fn();
    render(<DraftStudioHonestyBanners {...base} {...clarify} onAnswerClarify={onAnswerClarify} />);
    const card = screen.getByTestId("generation-clarify");
    expect(card.querySelectorAll("h3")).toHaveLength(1);
    expect(card.textContent).toMatch(/Suggested/);
    const radios = card.querySelectorAll<HTMLInputElement>('input[type="radio"]');
    expect(radios).toHaveLength(2);
    expect(radios[0].checked).toBe(true);
    fireEvent.click(radios[1]);
    fireEvent.click(screen.getByTestId("clarify-answer"));
    expect(onAnswerClarify).toHaveBeenCalledWith("As a standalone app");
  });

  it("falls back to a read-only list when no answer handler is wired", () => {
    render(<DraftStudioHonestyBanners {...base} {...clarify} />);
    expect(screen.queryByTestId("clarify-answer")).toBeNull();
    expect(screen.getByTestId("generation-clarify").textContent).toMatch(/On project tasks/);
  });

  it("turns Option A sandbox prove off on Odoo Online with a visible reason", () => {
    render(
      <DraftStudioHonestyBanners
        {...base}
        authoredOptionA
        isOdooOnline
        capabilityPrimaryOptionA
        optionALines={["Python compute on x_inspection.score"]}
      />,
    );
    expect(screen.getByTestId("option-a-prove")).toBeDisabled();
    expect(screen.getByTestId("option-a-prove-online").textContent).toMatch(
      /not available on Odoo Online/,
    );
  });
});
