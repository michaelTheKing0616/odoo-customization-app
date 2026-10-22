/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SettingsStageRail } from "./SettingsStageRail";

afterEach(() => cleanup());

describe("SettingsStageRail", () => {
  it("marks the current step", () => {
    render(<SettingsStageRail step={2} />);
    expect(screen.getByTestId("settings-step-status")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("settings-step-keys")).toHaveAttribute("data-state", "current");
    expect(screen.getByTestId("settings-step-audit")).toHaveAttribute("data-state", "todo");
  });
});
