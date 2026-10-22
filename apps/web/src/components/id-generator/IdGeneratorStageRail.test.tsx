import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { IdGeneratorStageRail } from "./IdGeneratorStageRail";

describe("IdGeneratorStageRail", () => {
  it("marks the current step", () => {
    render(<IdGeneratorStageRail step={3} />);
    expect(screen.getByTestId("id-generator-step-preview")).toHaveAttribute("data-state", "current");
    expect(screen.getByTestId("id-generator-step-source")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("id-generator-step-deliver")).toHaveAttribute("data-state", "todo");
  });
});
