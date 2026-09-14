/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ProjectHonestyBanners } from "./ProjectHonestyBanners";
import { projectsHonestyGate } from "@/lib/projects-journey";

afterEach(() => cleanup());

describe("ProjectHonestyBanners", () => {
  it("keeps glossary, score bars, and sandbox honesty", () => {
    render(
      <ProjectHonestyBanners
        gate={projectsHonestyGate({ writeMode: "standard", localSandboxUrl: true })}
        slotNote="1 of 3 active — archive anytime to free a slot."
      />,
    );
    expect(screen.getByTestId("projects-sandbox-gate").textContent).toMatch(/Generate UI/);
    expect(screen.getByTestId("projects-glossary").textContent).toMatch(/Promote stays human/);
    expect(screen.getByTestId("projects-score-bars-legend").textContent).toMatch(
      /Completeness is ModuleSpec hygiene/,
    );
    expect(screen.getByTestId("projects-slot-note").textContent).toMatch(/archive/);
  });

  it("surfaces production danger without blocking copy that auto-promotes", () => {
    render(
      <ProjectHonestyBanners gate={projectsHonestyGate({ writeMode: "production" })} />,
    );
    expect(screen.getByTestId("projects-production-gate").textContent).toMatch(/Prefer a sandbox/);
    expect(screen.getByTestId("projects-production-gate").textContent).toMatch(/Promote stays human/);
  });
});
