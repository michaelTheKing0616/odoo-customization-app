/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ProjectSessionBar } from "./ProjectSessionBar";

afterEach(() => cleanup());

describe("ProjectSessionBar", () => {
  it("shows draft chrome and the next action hint", () => {
    render(
      <ProjectSessionBar sessionState="draft" submitLabel="Select a draft, then Review vs live." />,
    );
    expect(screen.getByTestId("projects-session-state")).toHaveTextContent("Draft");
    expect(screen.getByTestId("projects-session-hint")).toHaveTextContent("Nothing writes to Odoo until Apply");
    expect(screen.getByTestId("projects-session-submit-hint")).toHaveTextContent("Review vs live");
  });

  it("labels applied and archived without exclamation marks", () => {
    const { rerender } = render(
      <ProjectSessionBar sessionState="applied" submitLabel="Review vs live, or open ModuleSpec to continue." />,
    );
    expect(screen.getByTestId("projects-session-state")).toHaveTextContent("Applied");
    expect(screen.getByTestId("projects-session-hint").textContent).not.toMatch(/!/);
    rerender(<ProjectSessionBar sessionState="archived" submitLabel="Un-archive to Apply." />);
    expect(screen.getByTestId("projects-session-state")).toHaveTextContent("Archived");
  });
});
