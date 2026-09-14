/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { JobAutopilotBriefPanel } from "./JobAutopilotBriefPanel";

afterEach(() => cleanup());

describe("JobAutopilotBriefPanel", () => {
  it("disables Run Autopilot when production is refused", () => {
    render(
      <JobAutopilotBriefPanel
        prompt="Bakery in NG"
        files={[]}
        busy={null}
        runBlocked
        runBlockedReason="Job Autopilot refuses write_mode=production."
        onPromptChange={vi.fn()}
        onFilesChange={vi.fn()}
        onPlan={vi.fn()}
        onRun={vi.fn()}
      />,
    );
    expect(screen.getByTestId("job-run-autopilot")).toBeDisabled();
    expect(screen.getByTestId("job-plan-packet")).not.toBeDisabled();
    expect(screen.getByTestId("job-run-blocked-hint").textContent).toMatch(
      /refuses write_mode=production/,
    );
  });
});
