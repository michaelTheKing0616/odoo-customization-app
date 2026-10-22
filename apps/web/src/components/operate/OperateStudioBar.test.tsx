/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OperateStudioBar } from "./OperateStudioBar";

describe("OperateStudioBar", () => {
  it("renders compact honesty bar with title / why / next test ids", () => {
    render(
      <OperateStudioBar
        testId="bulk-honesty-guide"
        tone="warning"
        title="Batch writes are not auto-undone"
        why="Successful rows stay written even when later rows fail."
        next="Dry-run first. Read the blast radius."
      />,
    );
    expect(screen.getByTestId("bulk-honesty-guide")).toBeInTheDocument();
    expect(screen.getByTestId("bulk-honesty-guide-title")).toHaveTextContent(
      /Batch writes are not auto-undone/,
    );
    expect(screen.getByTestId("bulk-honesty-guide-why").textContent?.length).toBeGreaterThan(5);
    expect(screen.getByTestId("bulk-honesty-guide-next").textContent?.toLowerCase()).toContain(
      "dry-run",
    );
    expect(screen.getByTestId("bulk-honesty-guide").textContent).not.toMatch(/\u2014|\u2013/);
  });
});
