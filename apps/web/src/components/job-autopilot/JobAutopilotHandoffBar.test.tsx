/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { JobAutopilotHandoffBar } from "./JobAutopilotHandoffBar";

afterEach(() => cleanup());

describe("JobAutopilotHandoffBar", () => {
  it("links ModuleSpec only when residual exists, never Projects or Expert", () => {
    render(
      <JobAutopilotHandoffBar
        connectionId="c1"
        targets={[]}
        targetId=""
        sandboxUrl="http://127.0.0.1:8069/web"
        sandboxLabel="Open sandbox"
        hasResult
        promoteReady
        hasResidualZip
        showModuleSpec
        busy={null}
        onTargetChange={vi.fn()}
        onPromote={vi.fn()}
        onDownloadReport={vi.fn()}
        onDownloadPdf={vi.fn()}
      />,
    );
    expect(screen.getByRole("link", { name: "ModuleSpec" })).toHaveAttribute(
      "href",
      "/connections/c1/modulespec",
    );
    expect(screen.getByRole("link", { name: "Draft Studio" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "App Studio" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Projects" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Expert" })).toBeNull();
    expect(screen.getByTestId("job-promote-or-handoff").textContent).toMatch(/Promote to target/);
  });

  it("uses Handoff when there is no residual zip", () => {
    render(
      <JobAutopilotHandoffBar
        connectionId="c1"
        targets={[]}
        targetId=""
        sandboxUrl={null}
        sandboxLabel="Open sandbox"
        hasResult
        promoteReady
        hasResidualZip={false}
        showModuleSpec={false}
        busy={null}
        onTargetChange={vi.fn()}
        onPromote={vi.fn()}
        onDownloadReport={vi.fn()}
        onDownloadPdf={vi.fn()}
      />,
    );
    expect(screen.getByTestId("job-promote-or-handoff").textContent).toBe("Handoff");
    expect(screen.queryByRole("link", { name: "ModuleSpec" })).toBeNull();
  });
});
