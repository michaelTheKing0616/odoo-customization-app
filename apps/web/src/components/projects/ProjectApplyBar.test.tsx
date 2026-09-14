/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectApplyBar } from "./ProjectApplyBar";
import type { ProjectRow } from "@/lib/projects-journey";

afterEach(() => cleanup());

const project: ProjectRow = {
  id: "p1",
  name: "Visitor log",
  template_id: "library",
  status: "draft",
  lifecycle_status: "active",
  spec_json: {},
};

describe("ProjectApplyBar", () => {
  it("keeps Review vs live, Apply, and Archive as verb-first CTAs", () => {
    const onReview = vi.fn();
    const onApply = vi.fn();
    const onArchive = vi.fn();
    render(
      <ProjectApplyBar
        project={project}
        busy={null}
        canMutate
        canApply
        onReview={onReview}
        onApply={onApply}
        onArchive={onArchive}
      />,
    );
    fireEvent.click(screen.getByTestId("projects-review"));
    fireEvent.click(screen.getByTestId("projects-apply"));
    fireEvent.click(screen.getByTestId("projects-archive"));
    expect(onReview).toHaveBeenCalledTimes(1);
    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onArchive).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("projects-review")).toHaveTextContent("Review vs live");
    expect(screen.queryByText(/!/)).toBeNull();
  });

  it("keeps Apply disabled until Review vs live has run", () => {
    const onApply = vi.fn();
    render(
      <ProjectApplyBar
        project={project}
        busy={null}
        canMutate
        canApply={false}
        applyBlocked="Open Review vs live before Apply"
        hasDiff={false}
        onReview={() => undefined}
        onApply={onApply}
        onArchive={() => undefined}
      />,
    );
    expect(screen.getByTestId("projects-apply")).toBeDisabled();
    expect(screen.getByTestId("projects-apply")).toHaveAttribute(
      "title",
      "Open Review vs live before Apply",
    );
  });
});
