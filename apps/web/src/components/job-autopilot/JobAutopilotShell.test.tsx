/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { JobAutopilotShell } from "./JobAutopilotShell";

afterEach(() => cleanup());

describe("JobAutopilotShell", () => {
  it("keeps Job Autopilot identity and sibling AI-studio links", () => {
    render(
      <JobAutopilotShell
        connectionId="c1"
        connectionName="Lab 19"
        journey={{ id: "brief" }}
      >
        <p>brief body</p>
      </JobAutopilotShell>,
    );
    expect(screen.getByTestId("job-autopilot")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Job Autopilot" })).toBeTruthy();
    expect(screen.getByText(/Lab 19/)).toBeTruthy();
    expect(screen.getByText(/sandbox-only/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Draft Studio" })).toHaveAttribute(
      "href",
      "/connections/c1/wizard",
    );
    expect(screen.getByRole("link", { name: "App Studio" })).toHaveAttribute(
      "href",
      "/connections/c1/studio",
    );
    expect(screen.getByTestId("job-autopilot-steps")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "ModuleSpec" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Projects" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Expert" })).toBeNull();
  });

  it("does not call a production connection a sandbox", () => {
    render(
      <JobAutopilotShell
        connectionId="c1"
        connectionName="Client production"
        writeMode="production"
        journey={{ id: "brief" }}
      >
        <p>brief body</p>
      </JobAutopilotShell>,
    );
    expect(screen.getByText(/refuses production/)).toBeTruthy();
    expect(screen.queryByText(/sandbox-only —/)).toBeNull();
  });
});
