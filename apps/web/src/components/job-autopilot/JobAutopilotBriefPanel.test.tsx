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

  it("shows what/why/next empty guide and one primary Run CTA", () => {
    render(
      <JobAutopilotBriefPanel
        prompt=""
        files={[]}
        busy={null}
        runBlocked={false}
        onPromptChange={vi.fn()}
        onFilesChange={vi.fn()}
        onPlan={vi.fn()}
        onRun={vi.fn()}
      />,
    );
    expect(screen.getByTestId("job-brief-empty").textContent).toMatch(/What:/);
    expect(screen.getByTestId("job-brief-empty").textContent).toMatch(/Why:/);
    expect(screen.getByTestId("job-brief-empty").textContent).toMatch(/Next:/);
    const run = screen.getByTestId("job-run-autopilot");
    expect(run.className).toMatch(/bg-accent|primary/);
  });
});

  it("demotes Run Autopilot when Promote owns the primary CTA", () => {
    render(
      <JobAutopilotBriefPanel
        prompt="Bakery in NG"
        files={[]}
        busy={null}
        runBlocked={false}
        runIsPrimary={false}
        onPromptChange={vi.fn()}
        onFilesChange={vi.fn()}
        onPlan={vi.fn()}
        onRun={vi.fn()}
      />,
    );
    expect(screen.getByTestId("job-run-autopilot").className).not.toMatch(/bg-accent/);
  });
