/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OpsHubStateGuide } from "./OpsHubStateGuide";
import { opsHubHonestyGuide, pickToolGuide } from "@/lib/operationsHubScreen";

describe("OpsHubStateGuide", () => {
  it("renders callout what / why / next without em dashes", () => {
    render(
      <OpsHubStateGuide testId="ops-hub-pick-guide" tone="accent" guide={pickToolGuide()} />,
    );
    expect(screen.getByTestId("ops-hub-pick-guide-title")).toBeInTheDocument();
    expect(screen.getByTestId("ops-hub-pick-guide-why").textContent?.length).toBeGreaterThan(5);
    expect(screen.getByTestId("ops-hub-pick-guide-next").textContent?.toLowerCase()).toContain(
      "bulk",
    );
    expect(screen.getByTestId("ops-hub-pick-guide").textContent).not.toMatch(/[—–]/);
  });

  it("renders quiet caption density for honesty", () => {
    render(
      <OpsHubStateGuide
        density="caption"
        testId="ops-hub-honesty"
        tone="warning"
        guide={opsHubHonestyGuide()}
      />,
    );
    expect(screen.getByTestId("ops-hub-honesty")).toHaveClass("oh-caption");
    expect(screen.getByTestId("ops-hub-honesty-title").textContent?.toLowerCase()).toContain(
      "ops tools can write",
    );
  });
});
