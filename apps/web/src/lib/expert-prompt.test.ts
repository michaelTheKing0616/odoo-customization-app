import { describe, expect, it } from "vitest";
import {
  buildExpertAskPayload,
  formatExpertDiagnosePrompt,
  isExpertSetupStackQuestion,
} from "./expert-prompt";

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

describe("buildExpertAskPayload", () => {
  it("merges a separate error paste into the question once", () => {
    const payload = buildExpertAskPayload("Why did this fail?", "AccessError: denied");
    expect(payload.question).toContain("Error log:");
    expect(payload.question).toContain("AccessError: denied");
    expect(payload.pastedError).toBe("AccessError: denied");
  });

  it("does not duplicate an error already in the main input", () => {
    const q = "Diagnose\n\nError log:\nAccessError";
    const payload = buildExpertAskPayload(q, "AccessError");
    expect(payload.question).toBe(q);
  });
});

describe("isExpertSetupStackQuestion", () => {
  it("treats module-stack asks as a fresh retrieval context", () => {
    expect(isExpertSetupStackQuestion("Which modules do I need for a law firm?")).toBe(true);
    expect(isExpertSetupStackQuestion("How does xpath inherit work?")).toBe(false);
  });
});

