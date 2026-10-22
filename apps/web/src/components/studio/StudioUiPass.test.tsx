/** @vitest-environment jsdom */
import type { ComponentProps } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ClarifyInterstitial } from "./ClarifyInterstitial";
import { StudioApplyBar } from "./StudioApplyBar";
import { StudioBriefScreen } from "./StudioBriefScreen";
import { StudioGeneratingCanvas, StudioGenerationFailed } from "./StudioGenerationStates";
import { StudioMobileTabs } from "./StudioMobileTabs";
import { StudioOptionAPanel } from "./StudioOptionAPanel";

vi.mock("@/lib/progress/use-stage-events", () => ({
  useStageEvents: () => ({ events: [], latest: null, error: null }),
}));

afterEach(() => cleanup());

const EM_OR_EN_DASH = /[\u2014\u2013]/;

const applyBase: ComponentProps<typeof StudioApplyBar> = {
  designerHref: "/connections/c1/designer",
  designerModel: "x_visitor_log",
  appIsLiveOnOdoo: false,
  fieldPack: false,
  hostFormName: "Visitor log",
  liveAppName: "Visitor log",
  goldOptionA: false,
  authoredOptionA: false,
  goldCanOpenSettings: false,
  goldInspect: null,
  openInOdooUrl: null,
  canApply: true,
  stockReuse: false,
  refuseClone: false,
  surfaceBlocked: false,
  applyBlocked: null,
  busy: null,
  onApply: () => undefined,
};

const optionABase: ComponentProps<typeof StudioOptionAPanel> = {
  goldOptionA: false,
  authoredOptionA: true,
  goldId: "",
  goldHonesty: "",
  goldSettings: null,
  goldHost: null,
  goldInspect: null,
  goldNeedsInvoicing: false,
  goldCanPromote: false,
  goldCanOpenSettings: false,
  goldPromoted: false,
  authoringPassed: true,
  authoringRetryable: false,
  hostInstallOffers: [],
  leftoverAuthoringFindings: [],
  isOdooOnline: false,
  busy: null,
  onInstallInvoicing: () => undefined,
  onDownloadZip: () => undefined,
  onProveSandbox: () => undefined,
  onPromote: () => undefined,
  onRetryAuthoring: () => undefined,
  onReverify: () => undefined,
  onInstallHost: () => undefined,
};

describe("App Studio UI pass (UI-S-20)", () => {
  it("brief: heading without eyebrow, teal primary, disabled reason is visible", () => {
    const onStart = vi.fn();
    render(
      <StudioBriefScreen prompt="short" busy={false} onPromptChange={vi.fn()} onStart={onStart} />,
    );
    const brief = screen.getByTestId("studio-brief");
    expect(screen.getByRole("heading", { name: "What should people do in Odoo?" })).toBeTruthy();
    expect(brief.querySelector(".studio-prompt-kicker")).toBeNull();
    const cta = screen.getByRole("button", { name: "See a preview" });
    expect(cta.className).toMatch(/btn-primary/);
    expect(cta.className).not.toMatch(/btn-brand/);
    expect(cta).toBeDisabled();
    expect(screen.getByText(/A sentence or two is enough/)).toBeTruthy();
    expect(brief.textContent).not.toMatch(EM_OR_EN_DASH);
  });

  it("brief: Ctrl/⌘ + Enter starts once the brief is long enough", () => {
    const onStart = vi.fn();
    render(
      <StudioBriefScreen
        prompt="Front desk signs visitors in and notifies the host."
        busy={false}
        onPromptChange={vi.fn()}
        onStart={onStart}
      />,
    );
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", metaKey: true });
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("brief: Flash toggle copy is plain language", () => {
    render(
      <StudioBriefScreen
        prompt="Front desk signs visitors in."
        busy={false}
        onPromptChange={vi.fn()}
        onStart={vi.fn()}
        flashAstEnrich={false}
        onFlashAstEnrichChange={vi.fn()}
      />,
    );
    const toggle = screen.getByTestId("studio-flash-ast-enrich-toggle");
    expect(toggle.textContent).toMatch(/Let AI add to the must-do list/);
    expect(toggle.textContent).not.toMatch(/deterministic floor|AST|AI_INTENT_LLM/);
  });

  it("diagnosis: Generate is the one primary and still sends the confirm answer", () => {
    const onAnswer = vi.fn();
    render(
      <ClarifyInterstitial
        clarification={{
          kind: "diagnosis",
          merge_key: "diagnosis",
          question: "Does this match?",
          help: "Visitor log app.",
          options: [],
          understanding: {
            title: "Visitor log",
            inherit_existing: false,
            needs_module: false,
            constraints: ["Notify the host"],
          },
        }}
        onAnswer={onAnswer}
      />,
    );
    const card = screen.getByTestId("studio-diagnosis");
    expect(screen.getByRole("heading", { name: "Check the diagnosis" })).toBeTruthy();
    const confirm = screen.getByTestId("studio-diagnosis-confirm");
    expect(confirm.textContent).toBe("Generate");
    expect(card.querySelectorAll(".btn-primary")).toHaveLength(1);
    expect(card.querySelector(".btn-brand")).toBeNull();
    fireEvent.click(confirm);
    expect(onAnswer.mock.calls[0][0]).toBe("diagnosis");
    expect(onAnswer.mock.calls[0][1]).toBe("confirm");
  });

  it("diagnosis: explains why Generate is off when no host form is chosen", () => {
    render(
      <ClarifyInterstitial
        clarification={{
          kind: "diagnosis",
          merge_key: "diagnosis",
          question: "Does this match?",
          options: [],
          understanding: { title: "PO markup", inherit_existing: true, host_model: "" },
        }}
        onAnswer={vi.fn()}
      />,
    );
    expect(screen.getByTestId("studio-diagnosis-confirm")).toBeDisabled();
    expect(screen.getByText("Choose the form this belongs on to generate.")).toBeTruthy();
  });

  it("generating: stage label in a live region, no fake percentage", () => {
    render(<StudioGeneratingCanvas runId={null} fallbackLabel="Drafting the Visitor log form" />);
    const status = screen.getByRole("status");
    expect(status.textContent).toMatch(/Drafting the Visitor log form/);
    expect(screen.getByTestId("studio-generating").textContent).not.toMatch(/\d+\s?%/);
  });

  it("failed: says what happened and offers Generate again plus Start over", () => {
    const onRetry = vi.fn();
    const onStartOver = vi.fn();
    render(
      <StudioGenerationFailed
        message="The model returned an incomplete draft."
        retrying={false}
        onRetry={onRetry}
        onStartOver={onStartOver}
      />,
    );
    const callout = screen.getByTestId("studio-generation-failed");
    expect(callout.textContent).toMatch(/Generation didn't finish/);
    expect(callout.textContent).toMatch(/incomplete draft/);
    fireEvent.click(screen.getByRole("button", { name: "Generate again" }));
    fireEvent.click(screen.getByRole("button", { name: "Start over" }));
    expect(onRetry).toHaveBeenCalled();
    expect(onStartOver).toHaveBeenCalled();
  });

  it("mobile tabs expose pressed state", () => {
    const onChange = vi.fn();
    render(<StudioMobileTabs value="preview" onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Form" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Refine" }));
    expect(onChange).toHaveBeenCalledWith("chat");
  });

  it("apply bar: blocked Install shows its reason as text, not only a tooltip", () => {
    render(<StudioApplyBar {...applyBase} stockReuse />);
    const apply = screen.getByTestId("studio-apply");
    expect(apply).toBeDisabled();
    expect(apply).toHaveAttribute("aria-describedby", "studio-apply-reason");
    expect(screen.getByTestId("studio-apply-reason").textContent).toMatch(/Job Autopilot/);
  });

  it("apply bar: no reason line when Install is available", () => {
    render(<StudioApplyBar {...applyBase} />);
    expect(screen.getByTestId("studio-apply")).not.toBeDisabled();
    expect(screen.queryByTestId("studio-apply-reason")).toBeNull();
  });

  it("brief: Enter alone starts when the brief is long enough", () => {
    const onStart = vi.fn();
    render(
      <StudioBriefScreen
        prompt="Front desk signs visitors in and notifies the host."
        busy={false}
        onPromptChange={vi.fn()}
        onStart={onStart}
      />,
    );
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });
    expect(onStart).toHaveBeenCalledTimes(1);
  });

  it("brief: Shift+Enter does not submit", () => {
    const onStart = vi.fn();
    render(
      <StudioBriefScreen
        prompt="Front desk signs visitors in and notifies the host."
        busy={false}
        onPromptChange={vi.fn()}
        onStart={onStart}
      />,
    );
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", shiftKey: true });
    expect(onStart).not.toHaveBeenCalled();
  });

  it("diagnosis card uses editorial diagnosis class and no eyebrow kicker", () => {
    render(
      <ClarifyInterstitial
        clarification={{
          kind: "diagnosis",
          merge_key: "diagnosis",
          question: "Does this match?",
          options: [],
          understanding: {
            title: "Visitor log",
            inherit_existing: false,
            needs_module: false,
            constraints: ["Notify the host"],
          },
        }}
        onAnswer={vi.fn()}
      />,
    );
    const card = screen.getByTestId("studio-diagnosis");
    expect(card.className).toMatch(/clarify-card--diagnosis/);
    expect(card.querySelector(".studio-prompt-kicker")).toBeNull();
    expect(card.textContent).not.toMatch(EM_OR_EN_DASH);
  });

  it("generating skeleton exposes desk paper ghost rows", () => {
    render(<StudioGeneratingCanvas runId={null} fallbackLabel="Drafting the Visitor log form" />);
    const root = screen.getByTestId("studio-generating");
    expect(root.querySelector(".studio-canvas-ghost-desk")).toBeTruthy();
    expect(root.querySelectorAll(".studio-canvas-ghost-row").length).toBeGreaterThanOrEqual(4);
  });


  it("premier: diagnosis craft panel is singular and defaults off", () => {
    render(
      <ClarifyInterstitial
        clarification={{
          kind: "diagnosis",
          merge_key: "diagnosis",
          question: "Does this match?",
          options: [],
          understanding: {
            title: "Visitor log",
            inherit_existing: false,
            needs_module: false,
            constraints: ["Notify the host"],
          },
        }}
        onAnswer={vi.fn()}
      />,
    );
    expect(screen.getAllByTestId("studio-diagnosis-approved-craft")).toHaveLength(1);
    // Extras are offered only when they apply; a short brief with no records gets supporting records.
    expect(screen.getByTestId("studio-craft-toggle-depth_seeds").getAttribute("aria-pressed")).toBe(
      "false",
    );
    expect(screen.getByTestId("studio-diagnosis").querySelectorAll(".btn-primary")).toHaveLength(1);
    expect(screen.getByTestId("studio-diagnosis").querySelector(".btn-brand")).toBeNull();
  });

  it("premier: failed recovery keeps one teal primary", () => {
    render(
      <StudioGenerationFailed
        message="The model returned an incomplete draft."
        retrying={false}
        onRetry={vi.fn()}
        onStartOver={vi.fn()}
      />,
    );
    const root = screen.getByTestId("studio-generation-failed");
    expect(root.querySelectorAll(".btn-primary")).toHaveLength(1);
    expect(root.querySelector(".btn-brand")).toBeNull();
    expect(root.textContent).not.toMatch(EM_OR_EN_DASH);
  });

  it("Option A panel fills only the next step", () => {
    const { rerender } = render(<StudioOptionAPanel {...optionABase} />);
    const panel = () => screen.getByTestId("studio-authored-option-a");
    expect(panel().querySelectorAll(".btn-primary")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Sandbox install & smoke" }).className).toMatch(
      /btn-primary/,
    );
    rerender(<StudioOptionAPanel {...optionABase} goldCanPromote />);
    expect(panel().querySelectorAll(".btn-primary")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Publish to this connection" }).className).toMatch(
      /btn-primary/,
    );
    expect(panel().querySelector(".btn-brand")).toBeNull();
    expect(panel().textContent).toMatch(/Do not click Install this app/);
  });
});
