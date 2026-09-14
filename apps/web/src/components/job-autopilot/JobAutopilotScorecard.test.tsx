/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { JobAutopilotScorecard } from "./JobAutopilotScorecard";

afterEach(() => cleanup());

describe("JobAutopilotScorecard", () => {
  it("keeps Completeness / Cert / Autopilot as three bars", () => {
    render(
      <JobAutopilotScorecard
        scorecard={{
          overall: 8.4,
          stack_fit: 8,
          stock_coverage: 9,
          data_load: 7,
          process_smoke: 9,
          findings: [],
          modulespec_completeness_note: "ModuleSpec 10.0 is not this bar.",
        }}
        smoke={{
          ok: true,
          named_process: "quote→invoice",
          message: "RPC smoke passed on sandbox.",
          steps: [{ name: "confirm", ok: true, detail: "sale.order confirmed" }],
        }}
        promoteReady
        stockOnly
      />,
    );
    expect(screen.getByTestId("job-scorecard-chip").textContent).toMatch(
      /Job scorecard: 8\.4\/10/,
    );
    expect(screen.getByTestId("job-scorecard-chip").textContent).toMatch(/smoke passed/);
    expect(screen.getByTestId("job-scorecard-legend").textContent).toMatch(
      /Completeness is ModuleSpec hygiene/,
    );
    expect(screen.getByTestId("job-scorecard-legend").textContent).toMatch(
      /Certification is the ship bar/,
    );
    expect(screen.getByTestId("job-scorecard-legend").textContent).toMatch(/Autopilot done-bar/);
    expect(screen.getByTestId("job-smoke-strip").textContent).toMatch(/Smoke passed/);
    expect(screen.getByTestId("job-score-overall").textContent).toMatch(
      /not Completeness, not Cert/,
    );
  });

  it("tells the operator not to promote when smoke failed", () => {
    render(
      <JobAutopilotScorecard
        scorecard={{
          overall: 4.2,
          stack_fit: 6,
          stock_coverage: 6,
          data_load: 2,
          process_smoke: 0,
          findings: [],
          modulespec_completeness_note: "Completeness is not this bar.",
        }}
        smoke={{
          ok: false,
          message: "Invoice wizard failed.",
          steps: [{ name: "invoice", ok: false, detail: "wizard refused" }],
        }}
      />,
    );
    expect(screen.getByTestId("job-scorecard-chip").textContent).toMatch(/smoke failed/);
    expect(screen.getByTestId("job-scorecard-chip").textContent).toMatch(/Do not promote/);
  });
});
