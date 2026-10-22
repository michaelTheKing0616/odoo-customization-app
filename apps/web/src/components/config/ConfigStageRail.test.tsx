/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ConfigStageRail } from "./ConfigStageRail";

afterEach(() => cleanup());

describe("ConfigStageRail", () => {
  it("marks the current step", () => {
    render(<ConfigStageRail step={3} />);
    expect(screen.getByTestId("config-step-recipes")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("config-step-configure")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("config-step-dry-run")).toHaveAttribute("data-state", "current");
    expect(screen.getByTestId("config-step-save")).toHaveAttribute("data-state", "todo");
  });
});
