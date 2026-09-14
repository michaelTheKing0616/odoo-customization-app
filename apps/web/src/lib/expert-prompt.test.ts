import { describe, expect, it } from "vitest";
import { formatExpertDiagnosePrompt } from "./expert-prompt";

describe("formatExpertDiagnosePrompt", () => {
  it("always includes an Error log block so Expert can see a blank paste", () => {
    expect(formatExpertDiagnosePrompt("Diagnose this error on my connection", "")).toBe(
      "Diagnose this error on my connection\n\nError log:\n",
    );
  });

  it("embeds the App Studio banner text", () => {
    const out = formatExpertDiagnosePrompt(
      "Diagnose this error on my connection",
      "Not Found (POST /api/ai/option-a/reverify)",
    );
    expect(out).toContain("Error log:");
    expect(out).toContain("POST /api/ai/option-a/reverify");
  });
});
