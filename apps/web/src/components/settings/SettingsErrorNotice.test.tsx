/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/expert-diagnostics", () => ({
  diagnoseWithExpert: vi.fn(),
}));

import { SettingsErrorNotice } from "./SettingsErrorNotice";

afterEach(() => cleanup());

describe("SettingsErrorNotice", () => {
  it("shows classified why and next", () => {
    render(
      <SettingsErrorNotice message="timed out" context="load" />,
    );
    expect(screen.getByTestId("settings-error-notice")).toBeTruthy();
    expect(screen.getByTestId("settings-error-why").textContent).toMatch(/took too long/i);
    expect(screen.getByTestId("settings-error-next").textContent.length).toBeGreaterThan(10);
    expect(screen.getByRole("button", { name: /Diagnose with Expert/i })).toBeTruthy();
  });
});
