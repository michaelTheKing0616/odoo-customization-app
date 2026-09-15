/** @vitest-environment jsdom */
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PresenterOverlay } from "@/components/live-demo-copilot/PresenterOverlay";
import type { LiveDemoAnswer } from "@/lib/api";

function answer(partial: Partial<LiveDemoAnswer> & Pick<LiveDemoAnswer, "id" | "question">): LiveDemoAnswer {
  return {
    session_id: "s1",
    speaker_name: "Client",
    bullets: ["Bullet one", "Bullet two"],
    confidence: "high",
    confidence_flag: null,
    grounded: true,
    declined: false,
    citations: [],
    status: "ready",
    stage1_reason: "odoo_question",
    stage1_score: "0.9",
    model_used: "test",
    created_at: "2026-09-15T00:00:00Z",
    ...partial,
  };
}

describe("PresenterOverlay", () => {
  afterEach(() => cleanup());

  it("shows empty waiting state", () => {
    render(<PresenterOverlay answers={[]} showShareGuidance={false} />);
    expect(screen.getByTestId("presenter-empty")).toHaveTextContent(/Waiting for Odoo questions/);
    expect(screen.getByTestId("presenter-not-for-share")).toHaveTextContent(/Not for screen share/);
  });

  it("renders the latest answer bullets", () => {
    render(
      <PresenterOverlay
        answers={[
          answer({
            id: "a1",
            question: "Can Odoo do multi-company?",
            bullets: ["Yes with multi-company", "Chart of accounts per company"],
          }),
        ]}
        showShareGuidance={false}
      />,
    );
    expect(screen.getByTestId("presenter-question")).toHaveTextContent(/multi-company/);
    expect(screen.getByTestId("presenter-bullets")).toHaveTextContent(/Chart of accounts/);
    expect(screen.getByTestId("presenter-confidence")).toHaveTextContent(/high confidence/);
  });

  it("surfaces low-confidence flag", () => {
    render(
      <PresenterOverlay
        answers={[
          answer({
            id: "a2",
            question: "Will this upgrade safely?",
            confidence: "low",
            confidence_flag: "Not fully certain — worth confirming before stating this to the client.",
            bullets: ["Depends on custom modules"],
          }),
        ]}
        showShareGuidance={false}
      />,
    );
    expect(screen.getByTestId("presenter-confidence")).toHaveTextContent(/low confidence/);
    expect(screen.getByTestId("presenter-confidence-flag")).toHaveTextContent(/Not fully certain/);
  });
});
