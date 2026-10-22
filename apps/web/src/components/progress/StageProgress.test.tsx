import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { StageProgress } from "./StageProgress";

vi.mock("@/lib/progress/use-stage-events", () => ({
  useStageEvents: vi.fn(),
}));

import { useStageEvents } from "@/lib/progress/use-stage-events";

describe("StageProgress", () => {
  beforeEach(() => {
    vi.mocked(useStageEvents).mockReturnValue({
      events: [{ run_id: "r1", stage: "expert_retrieve", detail: "docs" }],
      latest: { run_id: "r1", stage: "expert_retrieve", detail: "docs" },
      error: null,
    });
  });

  it("shows stage label and keeps technical detail closed by default", () => {
    render(<StageProgress runId="r1" active fallbackLabel="Fallback" />);
    expect(screen.getByTestId("stage-progress-label").textContent).toMatch(/Retrieving sources/);
    expect(screen.queryByTestId("stage-progress-details")).toBeNull();
    fireEvent.click(screen.getByTestId("stage-progress-details-toggle"));
    expect(screen.getByTestId("stage-progress-details").textContent).toMatch(/docs/);
  });

  it("uses the fallback label until the first stage event arrives", () => {
    vi.mocked(useStageEvents).mockReturnValue({ events: [], latest: null, error: null });
    render(<StageProgress runId={null} active fallbackLabel="Drafting the Visitor log form" />);
    expect(screen.getAllByTestId("stage-progress-label").at(-1)?.textContent).toBe(
      "Drafting the Visitor log form",
    );
  });

  it("requires Continue or Stop on tool_call_limit", () => {
    vi.mocked(useStageEvents).mockReturnValue({
      events: [{ run_id: "r1", stage: "tool_call_limit", detail: "120 calls" }],
      latest: { run_id: "r1", stage: "tool_call_limit", detail: "120 calls" },
      error: null,
    });
    const onContinue = vi.fn();
    const onStop = vi.fn();
    render(
      <StageProgress runId="r1" active onContinue={onContinue} onStop={onStop} />,
    );
    expect(screen.getByTestId("tool-call-limit-prompt")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("tool-call-limit-continue"));
    expect(onContinue).toHaveBeenCalledTimes(1);
    expect(onStop).not.toHaveBeenCalled();
  });
});
