import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { JournalStageRail } from "@/components/journal/JournalStageRail";

describe("JournalStageRail", () => {
  it("marks Inspect as current on step 2", () => {
    render(<JournalStageRail step={2} />);
    expect(screen.getByTestId("journal-step-timeline")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("journal-step-inspect")).toHaveAttribute("data-state", "current");
    expect(screen.getByTestId("journal-step-roll-back")).toHaveAttribute("data-state", "todo");
  });
});
