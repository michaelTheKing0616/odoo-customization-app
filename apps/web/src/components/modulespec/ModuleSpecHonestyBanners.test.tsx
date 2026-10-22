/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ModuleSpecHonestyBanners } from "./ModuleSpecHonestyBanners";

afterEach(() => cleanup());

describe("ModuleSpecHonestyBanners", () => {
  it("keeps the three score bars and stock-reuse honesty", () => {
    render(
      <ModuleSpecHonestyBanners
        stockReuse
        completenessNote="Completeness 10.0/10 is app plan hygiene, not go-live."
      />,
    );
    expect(screen.getByTestId("modulespec-stock-reuse").textContent).toMatch(/Job Autopilot/);
    expect(screen.getByTestId("modulespec-stock-reuse").textContent).toMatch(/Do not Generate UI/);
    expect(screen.getByTestId("modulespec-score-bars-legend").textContent).toMatch(
      /Completeness is app plan hygiene/,
    );
    expect(screen.getByTestId("modulespec-completeness-note").textContent).toMatch(/not go-live/);
  });
});
