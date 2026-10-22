/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { JobAutopilotRecipeRail } from "./JobAutopilotRecipeRail";

afterEach(() => cleanup());

describe("JobAutopilotRecipeRail", () => {
  it("keeps payments → inbound → messaging → hardware → statutory order", () => {
    render(
      <JobAutopilotRecipeRail
        detected={["messaging", "payments"]}
        connectors={{
          ran: ["payments"],
          failed: [],
          skipped_ids: [],
          steps: [{ name: "payments", ok: true }],
        }}
      />,
    );
    const rail = screen.getByTestId("job-recipe-rail");
    const ids = Array.from(rail.querySelectorAll("[data-recipe]")).map((el) =>
      el.getAttribute("data-recipe"),
    );
    expect(ids).toEqual([
      "payments",
      "inbound_orders",
      "messaging",
      "hardware",
      "statutory_payroll",
    ]);
    expect(rail.querySelector('[data-recipe="payments"]')?.getAttribute("data-state")).toBe(
      "done",
    );
    expect(rail.textContent).toMatch(/Publishing stays a step you confirm/);
    expect(rail.textContent).not.toMatch(/\u2014/);
  });
});
