import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { briefWantsAi, effectiveAiStep } from "./brief-wants-ai";
import { StudioBriefScreen as StudioBriefScreenModule } from "./StudioBriefScreen";

const LONG = Array.from({ length: 70 }, (_, i) => `word${i}`).join(" ");

describe("AI step default", () => {
  it("is on for long or structured briefs, off for short ones", () => {
    expect(briefWantsAi("Add a Priority field to tasks")).toBe(false);
    expect(briefWantsAi(LONG)).toBe(true);
    expect(briefWantsAi("# Customer Health\nTrack accounts")).toBe(true);
    expect(briefWantsAi("1. a\n2. b\n3. c")).toBe(true);
    expect(briefWantsAi("")).toBe(false);
  });

  it("respects an explicit uncheck or check", () => {
    expect(effectiveAiStep(null, LONG)).toBe(true);
    expect(effectiveAiStep(false, LONG)).toBe(false);
    expect(effectiveAiStep(true, "short")).toBe(true);
    expect(effectiveAiStep(null, "short")).toBe(false);
  });

  it("checkbox renders checked for a long brief by default", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Screen = StudioBriefScreenModule as any;
    const { rerender } = render(
      <Screen prompt={LONG} flashAstEnrich={effectiveAiStep(null, LONG)} onFlashAstEnrichChange={vi.fn()} />,
    );
    expect((screen.getByRole("checkbox") as HTMLInputElement).checked).toBe(true);
    rerender(<Screen prompt="short" flashAstEnrich={effectiveAiStep(null, "short")} onFlashAstEnrichChange={vi.fn()} />);
    expect((screen.getByRole("checkbox") as HTMLInputElement).checked).toBe(false);
  });
});
