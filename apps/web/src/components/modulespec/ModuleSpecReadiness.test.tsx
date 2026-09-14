/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ModuleSpecReadiness } from "./ModuleSpecReadiness";
import { localReadiness } from "@/lib/modulespec-journey";
import { emptyModuleSpec } from "@/lib/modulespec-types";

afterEach(() => cleanup());

describe("ModuleSpecReadiness", () => {
  it("renders local blocking items and live validate CTA", () => {
    const onValidate = vi.fn();
    render(
      <ModuleSpecReadiness
        report={localReadiness(emptyModuleSpec())}
        canValidate
        onValidate={onValidate}
      />,
    );
    expect(screen.getByTestId("modulespec-readiness-headline").textContent).toMatch(
      /blocking issue/,
    );
    expect(screen.getByTestId("modulespec-readiness-body").textContent).toMatch(
      /Completeness is ModuleSpec hygiene/,
    );
    fireEvent.click(screen.getByTestId("modulespec-validate"));
    expect(onValidate).toHaveBeenCalledTimes(1);
  });

  it("shows live validate results without calling them Certification", () => {
    render(
      <ModuleSpecReadiness
        report={localReadiness({
          technical_name: "visitor_log",
          display_name: "Visitor log",
          models: [
            {
              model: "x_visitor_log",
              fields: [{ name: "x_name", ttype: "char", string: "Name" }],
            },
          ],
        })}
        live={{
          ok: false,
          fail_count: 1,
          warn_count: 0,
          message: "Missing inherit host",
          items: [
            {
              item_id: "1",
              category: "model",
              status: "fail",
              message: "sale.order is not installed",
            },
          ],
        }}
        onValidate={vi.fn()}
      />,
    );
    expect(screen.getByTestId("modulespec-live-validate").textContent).toMatch(/1 fail/);
    expect(screen.getByTestId("modulespec-live-validate").textContent).not.toMatch(/Gold/);
  });
});
