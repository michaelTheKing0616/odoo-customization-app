/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ProjectDiffPanel } from "./ProjectDiffPanel";
import type { ProjectDiffOut } from "@/lib/api";

afterEach(() => cleanup());

const diff: ProjectDiffOut = {
  ok: true,
  message: "Ready",
  to_create_models: ["x_visitor_log"],
  existing_models: ["res.partner"],
  to_create_fields: ["x_visitor_log.x_name"],
  existing_fields: ["res.partner.name"],
  conflicts: ["x_name type mismatch"],
};

describe("ProjectDiffPanel", () => {
  it("elevates a trustworthy change review with sentence-case filters", () => {
    render(<ProjectDiffPanel diff={diff} />);
    expect(screen.getByTestId("project-diff-panel")).toBeTruthy();
    expect(screen.getByTestId("project-diff-headline").textContent).toMatch(/conflict/i);
    expect(screen.getByTestId("project-diff-stats").textContent).toMatch(/To create/);
    expect(screen.getByRole("button", { name: "Already live" })).toBeTruthy();
    expect(screen.getByText("x_name type mismatch")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Already live" }));
    expect(screen.getByText("Models already live")).toBeTruthy();
    expect(screen.queryByText("x_name type mismatch")).toBeNull();
    expect(screen.getByTestId("project-diff-panel").textContent).toMatch(/Promote stays human/);
    expect(screen.getByTestId("project-diff-panel").textContent).not.toMatch(/!/);
  });
});
