import { afterEach, describe, expect, it } from "vitest";
import {
  briefTextForJobAutopilot,
  jobAutopilotBriefStorageKey,
  readJobAutopilotBrief,
  stashJobAutopilotBrief,
} from "./job-brief-handoff";

describe("briefTextForJobAutopilot", () => {
  it("prefers the structured operator brief over the raw prompt", () => {
    const text = briefTextForJobAutopilot(
      {
        _user_prompt: "raw paste",
        _operator_brief: { formatted: "# Operator brief\n## Goal\nStand up POS" },
      },
      "textarea leftover",
    );
    expect(text).toContain("Stand up POS");
    expect(text).not.toBe("raw paste");
  });

  it("falls back to _user_prompt then the wizard textarea", () => {
    expect(briefTextForJobAutopilot({ _user_prompt: "  cashiers sell  " }, "x")).toBe(
      "cashiers sell",
    );
    expect(briefTextForJobAutopilot({}, "  typed in wizard  ")).toBe("typed in wizard");
    expect(briefTextForJobAutopilot(null, "")).toBe("");
  });
});

describe("stashJobAutopilotBrief", () => {
  const id = "conn-handoff";

  afterEach(() => {
    sessionStorage.removeItem(jobAutopilotBriefStorageKey(id));
  });

  it("round-trips a brief for the same connection", () => {
    stashJobAutopilotBrief(id, "  # Operator brief\n");
    expect(readJobAutopilotBrief(id)).toBe("# Operator brief");
  });

  it("ignores empty briefs", () => {
    stashJobAutopilotBrief(id, "   ");
    expect(readJobAutopilotBrief(id)).toBeNull();
  });
});
