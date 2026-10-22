import { describe, expect, it } from "vitest";
import {
  PRIMARY_CTA,
  emptyScriptRunnerGuide,
  idleScriptRunnerGuide,
  observerScriptRunnerGuide,
  sanitizeScriptRunnerCopy,
  scriptRunnerErrorGuide,
  scriptRunnerHonestyGuide,
  scriptRunnerStepFromState,
  succeededScriptRunnerGuide,
} from "@/lib/scriptRunnerScreen";

describe("scriptRunnerScreen", () => {
  it("names Run script as the primary CTA", () => {
    expect(PRIMARY_CTA).toBe("Run script");
  });

  it("steps Compose → Confirm → Run without a test run stage", () => {
    expect(
      scriptRunnerStepFromState({
        hasScript: true,
        confirmOpen: false,
        busy: false,
        hasResult: false,
      }),
    ).toBe(1);
    expect(
      scriptRunnerStepFromState({
        hasScript: true,
        confirmOpen: true,
        busy: false,
        hasResult: false,
      }),
    ).toBe(2);
    expect(
      scriptRunnerStepFromState({
        hasScript: true,
        confirmOpen: false,
        busy: true,
        hasResult: false,
      }),
    ).toBe(3);
    expect(
      scriptRunnerStepFromState({
        hasScript: true,
        confirmOpen: false,
        busy: false,
        hasResult: true,
      }),
    ).toBe(3);
  });

  it("states honesty: no test run, live RPC after confirm", () => {
    const guide = scriptRunnerHonestyGuide();
    expect(guide.title.toLowerCase()).toContain("no test run");
    expect(guide.why.toLowerCase()).toMatch(/real|live|credentials/);
    expect(sanitizeScriptRunnerCopy("a — b – c")).toBe("a - b - c");
  });

  it("covers empty, idle, and observer what/why/next", () => {
    expect(emptyScriptRunnerGuide().next.toLowerCase()).toContain("run script");
    expect(idleScriptRunnerGuide().why.toLowerCase()).toContain("confirm");
    expect(observerScriptRunnerGuide().title.toLowerCase()).toContain("observer");
  });

  it("classifies run errors and success with snapshot honesty", () => {
    const err = scriptRunnerErrorGuide("run", "Failed to fetch");
    expect(err.why.toLowerCase()).toMatch(/could not reach|network|api/);
    const ok = succeededScriptRunnerGuide({ writeCount: 2, snapshotId: "snap-1" });
    expect(ok.why).toContain("2 writes");
    expect(ok.next).toContain("snap-1");
    expect(ok.next.toLowerCase()).toContain("partly recoverable");
  });
});
