/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FleetStateGuide } from "./FleetStateGuide";
import { fleetHonestyGuide, idleFleetGuide } from "@/lib/fleetCommandScreen";

describe("FleetStateGuide", () => {
  it("renders what / why / next without em dashes", () => {
    render(
      <FleetStateGuide testId="fleet-idle-guide" tone="accent" guide={idleFleetGuide()} />,
    );
    expect(screen.getByTestId("fleet-idle-guide-title")).toBeInTheDocument();
    expect(screen.getByTestId("fleet-idle-guide-why").textContent?.length).toBeGreaterThan(5);
    expect(screen.getByTestId("fleet-idle-guide-next").textContent?.toLowerCase()).toContain(
      "open a client",
    );
    expect(screen.getByTestId("fleet-idle-guide").textContent).not.toMatch(/[—–]/);
  });

  it("renders quiet caption density for honesty", () => {
    render(
      <FleetStateGuide
        density="caption"
        testId="fleet-honesty"
        tone="neutral"
        guide={fleetHonestyGuide()}
      />,
    );
    expect(screen.getByTestId("fleet-honesty")).toHaveClass("fc-caption");
    expect(screen.getByTestId("fleet-honesty-title").textContent?.toLowerCase()).toContain(
      "counts span",
    );
  });
});
