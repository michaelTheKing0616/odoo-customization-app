/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { JobAutopilotHonestyBanners } from "./JobAutopilotHonestyBanners";
import { jobAutopilotGate } from "@/lib/job-autopilot-journey";

afterEach(() => cleanup());

describe("JobAutopilotHonestyBanners", () => {
  it("makes production refuse unmistakable and keeps the three score bars", () => {
    render(
      <JobAutopilotHonestyBanners
        gate={jobAutopilotGate({ writeMode: "production" })}
        contractNote="ModuleSpec completeness 10.0 is not Autopilot smoke."
      />,
    );
    expect(screen.getByTestId("job-autopilot-production-gate")).toBeTruthy();
    expect(screen.getByTestId("job-autopilot-production-refuse").textContent).toMatch(
      /stays disabled/,
    );
    expect(screen.getByTestId("job-autopilot-gate-body").textContent).toMatch(
      /refuses write_mode=production/,
    );
    expect(screen.getByTestId("job-score-bars-legend").textContent).toMatch(
      /Completeness is ModuleSpec hygiene/,
    );
    expect(screen.getByTestId("job-score-bars-legend").textContent).toMatch(
      /Autopilot done-bar/,
    );
    expect(screen.getByTestId("job-autopilot-contract-note").textContent).toMatch(
      /not Autopilot smoke/,
    );
  });

  it("marks sandbox as the intended unattended path", () => {
    render(
      <JobAutopilotHonestyBanners
        gate={jobAutopilotGate({ writeMode: "standard", sandbox: true })}
        showOverviewNote
      />,
    );
    expect(screen.getByTestId("job-autopilot-sandbox-gate")).toBeTruthy();
    expect(screen.getByTestId("job-autopilot-gate-body").textContent).toMatch(
      /RPC process smoke/,
    );
    expect(screen.getByText(/Overview checklist is not this job/)).toBeTruthy();
  });
});
