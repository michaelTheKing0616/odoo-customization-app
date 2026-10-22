/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BulkOpRail } from "./BulkOpRail";

describe("BulkOpRail", () => {
  it("marks the current stage", () => {
    render(<BulkOpRail step={3} />);
    expect(screen.getByTestId("bulk-step-dry-run")).toHaveAttribute("data-state", "current");
    expect(screen.getByTestId("bulk-step-model")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("bulk-step-run")).toHaveAttribute("data-state", "todo");
  });
});
