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
