/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WizardErrorNotice } from "./WizardErrorNotice";

afterEach(() => cleanup());

describe("WizardErrorNotice", () => {
  it("shows what happened, why, and the next step before a draft exists", () => {
    render(
      <WizardErrorNotice
        message="The model provider did not answer within 120 seconds."
        hasDraft={false}
      />,
    );
    expect(screen.getByTestId("error-notice-message").textContent).toMatch(/120 seconds/);
    expect(screen.getByTestId("error-notice-why").textContent).toMatch(/took too long/);
    expect(screen.getByTestId("error-notice-next").textContent).toMatch(/never writes to Odoo/);
    expect(screen.getByRole("button", { name: "Diagnose with Expert" })).toBeTruthy();
  });

  it("reassures that the draft survives and offers Dismiss when wired", () => {
    const onDismiss = vi.fn();
    render(<WizardErrorNotice message="Validate failed" hasDraft onDismiss={onDismiss} />);
    expect(screen.queryByTestId("error-notice-why")).toBeNull();
    expect(screen.getByTestId("error-notice-next").textContent).toMatch(/draft is still here/);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
