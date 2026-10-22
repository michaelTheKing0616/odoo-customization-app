/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DraftStudioApplyBar } from "./DraftStudioApplyBar";

afterEach(() => cleanup());

const base = {
  canDraft: true,
  canApply: true,
  hasDraft: false,
  aiBusy: false,
  busy: false,
  zipBusy: false,
  finisherComplete: true,
  refuseClone: false,
  stockReuse: false,
  moduleDelivery: false,
  zipLocked: false,
  generateUiBlocked: null,
  overlapPending: false,
  needsConnectReview: false,
  connectApproved: false,
  designerHref: "/connections/c1/designer",
  designerModel: "x_inspection",
  jobAutopilotHref: "/connections/c1/job",
  applied: false,
  onCreateDraft: vi.fn(),
  onApply: vi.fn(),
  onDownloadZip: vi.fn(),
  onOpenModuleSpec: vi.fn(),
  onStashJobBrief: vi.fn(),
};

function filled(container: HTMLElement) {
  // Button primary variant is the only filled accent control.
  return Array.from(container.querySelectorAll("button, a")).filter((el) =>
    /bg-accent(?![-\w])/.test(el.className),
  );
}

describe("DraftStudioApplyBar", () => {
  it("prompt stage: one primary named Generate the draft, no dead Apply buttons", () => {
    const onCreateDraft = vi.fn();
    const { container } = render(
      <DraftStudioApplyBar {...base} onCreateDraft={onCreateDraft} promptLength={40} />,
    );
    const cta = screen.getByTestId("create-draft");
    expect(cta.textContent).toBe("Generate the draft");
    expect(screen.queryByTestId("apply-to-odoo")).toBeNull();
    expect(screen.queryByTestId("open-modulespec")).toBeNull();
    expect(filled(container)).toHaveLength(1);
    fireEvent.click(cta);
    expect(onCreateDraft).toHaveBeenCalledTimes(1);
  });

  it("prompt stage: a disabled primary says why in visible text", () => {
    render(<DraftStudioApplyBar {...base} canDraft={false} promptLength={0} />);
    const cta = screen.getByTestId("create-draft");
    expect(cta).toBeDisabled();
    const reason = screen.getByTestId("create-draft-reason");
    expect(reason.textContent).toMatch(/Describe what you need/);
    expect(cta.getAttribute("aria-describedby")).toBe(reason.id);
  });

  it("prompt stage: connect review reason when component grain is unapproved", () => {
    render(
      <DraftStudioApplyBar
        {...base}
        canDraft={false}
        needsConnectReview
        connectApproved={false}
        promptLength={40}
      />,
    );
    expect(screen.getByTestId("create-draft-reason").textContent).toMatch(/connect points/);
  });

  it("review stage: Apply is the single primary and regenerate is secondary", () => {
    const { container } = render(<DraftStudioApplyBar {...base} hasDraft />);
    expect(screen.getByTestId("create-draft").textContent).toBe("Regenerate the draft");
    expect(screen.getByTestId("apply-to-odoo").textContent).toBe("Apply to Odoo");
    const primaries = filled(container);
    expect(primaries).toHaveLength(1);
    expect(primaries[0]).toBe(screen.getByTestId("apply-to-odoo"));
  });

  it("review stage: blocked Apply keeps the primary slot and explains itself", () => {
    render(
      <DraftStudioApplyBar
        {...base}
        hasDraft
        canApply={false}
        generateUiBlocked="Probe this connection first"
      />,
    );
    expect(screen.getByTestId("apply-to-odoo")).toBeDisabled();
    expect(screen.getByTestId("apply-to-odoo-reason").textContent).toBe(
      "Probe this connection first",
    );
  });

  it("review stage: stock reuse routes to Job Autopilot as the only primary", () => {
    const { container } = render(<DraftStudioApplyBar {...base} hasDraft stockReuse />);
    expect(screen.queryByTestId("apply-to-odoo")).toBeNull();
    expect(screen.getByTestId("open-job-autopilot")).toBeTruthy();
    expect(filled(container)).toHaveLength(1);
    expect(screen.getByTestId("apply-to-odoo-reason").textContent).toMatch(/Job Autopilot/);
  });

  it("after apply: Apply again is secondary so Open app in Odoo can lead", () => {
    const { container } = render(<DraftStudioApplyBar {...base} hasDraft applied />);
    expect(screen.getByTestId("apply-to-odoo").textContent).toBe("Apply again");
    expect(filled(container)).toHaveLength(0);
  });
});
