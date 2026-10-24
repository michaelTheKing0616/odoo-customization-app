/** @vitest-environment jsdom */
/** BV-UI-WIRE oracle: VerifyRunPanel fetches one run and feeds EvidenceViewer. */
import React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { VerifyRun } from "@/lib/api/botVerify";

const getVerifyRun = vi.fn();
vi.mock("@/lib/api/botVerify", () => ({
  botVerifyApi: {
    getVerifyRun: (...a: unknown[]) => getVerifyRun(...a),
    verifyArtifactUrl: (c: string, r: string, a: string) => `/api/connections/${c}/verify-runs/${r}/artifacts/${a}`,
  },
}));

import { VerifyRunPanel } from "./VerifyRunPanel";

const RUN: VerifyRun = {
  run_id: "r1",
  changeset_id: "cs1",
  status: "passed",
  started_at: "2026-10-24T09:00:00Z",
  finished_at: "2026-10-24T09:01:00Z",
  layers: [
    {
      layer: "walkthrough",
      status: "passed",
      reason: null,
      checks: [],
      steps: [
        { index: 0, op_index: 0, action: "open", target: "res.partner form", passed: true, screenshot_id: "shot0", dom_assertion: null },
      ],
    },
  ],
};

const BANNED = /\b(500|404|403|stack|exception|undefined|null|traceback|error code)\b/i;
const httpErr = (status: number, detail: unknown = null) => Object.assign(new Error(`Request failed (${status})`), { status, detail });

beforeEach(() => {
  getVerifyRun.mockReset();
  vi.stubGlobal(
    "matchMedia",
    vi.fn((q: string) => ({ matches: false, media: q, onchange: null, addEventListener: vi.fn(), removeEventListener: vi.fn(), addListener: vi.fn(), removeListener: vi.fn(), dispatchEvent: vi.fn() })),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const state = () => screen.getByTestId("evidence-viewer").getAttribute("data-state");

describe("VerifyRunPanel", () => {
  it("AC1 fetches once on mount and renders the run with same-origin artifact urls", async () => {
    getVerifyRun.mockResolvedValue(RUN);
    render(<VerifyRunPanel connectionId="c 1" runId="r1" />);
    await waitFor(() => expect(state()).toBe("ready"));
    expect(getVerifyRun).toHaveBeenCalledTimes(1);
    expect(getVerifyRun).toHaveBeenCalledWith("c 1", "r1");
    for (const img of Array.from(document.querySelectorAll("img"))) {
      const src = img.getAttribute("src") || "";
      expect(src.startsWith("/api/connections/")).toBe(true);
      expect(src).toContain("/artifacts/shot0");
    }
  });

  it("AC2 shows loading while the request is pending", async () => {
    getVerifyRun.mockReturnValue(new Promise(() => {}));
    render(<VerifyRunPanel connectionId="c1" runId="r1" />);
    expect(state()).toBe("loading");
  });

  it("AC2 server error shows plain copy and Retry refetches", async () => {
    getVerifyRun.mockRejectedValueOnce(httpErr(500, "Traceback ...")).mockResolvedValueOnce(RUN);
    render(<VerifyRunPanel connectionId="c1" runId="r1" />);
    await waitFor(() => expect(state()).toBe("error"));
    const viewer = screen.getByTestId("evidence-viewer");
    expect(viewer.textContent || "").not.toMatch(BANNED);
    expect(viewer.textContent || "").toMatch(/not changed|unchanged/i);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /try again|retry/i }));
    });
    await waitFor(() => expect(state()).toBe("ready"));
    expect(getVerifyRun).toHaveBeenCalledTimes(2);
  });

  it("AC2 403 with a group shows the denied state", async () => {
    getVerifyRun.mockRejectedValue(httpErr(403, { code: "ROLE_DENIED", message: "x", detail: { group: "Verify viewer" }, retry_after_s: null }));
    render(<VerifyRunPanel connectionId="c1" runId="r1" />);
    await waitFor(() => expect(state()).toBe("denied"));
    expect(screen.getByTestId("evidence-viewer").textContent).toContain("Verify viewer");
  });

  it("AC2 404 shows the empty state with no existence leak", async () => {
    getVerifyRun.mockRejectedValue(httpErr(404, { code: "NOT_FOUND", message: "run r1 not found", detail: null, retry_after_s: null }));
    render(<VerifyRunPanel connectionId="c1" runId="r1" />);
    await waitFor(() => expect(state()).toBe("empty"));
    const t = screen.getByTestId("evidence-viewer").textContent || "";
    expect(t).not.toContain("r1");
    expect(t).not.toMatch(BANNED);
  });

  it("ignores a stale response after unmount", async () => {
    let resolve: (r: VerifyRun) => void = () => {};
    getVerifyRun.mockReturnValue(new Promise<VerifyRun>((r) => (resolve = r)));
    const { unmount } = render(<VerifyRunPanel connectionId="c1" runId="r1" />);
    unmount();
    await act(async () => resolve(RUN));
  });
});
