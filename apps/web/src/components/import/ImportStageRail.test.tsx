/** @vitest-environment jsdom */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ImportStageRail } from "@/components/import/ImportStageRail";

describe("ImportStageRail", () => {
  it("marks Validate as current after dry-run", () => {
    render(
      <div className="import-operate">
        <ImportStageRail step={3} />
      </div>,
    );
    expect(screen.getByTestId("import-step-validate")).toHaveAttribute("data-state", "current");
    expect(screen.getByTestId("import-step-upload")).toHaveAttribute("data-state", "done");
    expect(screen.getByTestId("import-step-commit")).toHaveAttribute("data-state", "todo");
  });
});
