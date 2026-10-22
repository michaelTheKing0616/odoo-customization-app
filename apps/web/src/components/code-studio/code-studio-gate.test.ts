import { describe, expect, it } from "vitest";
import type { CodeStudioTestRunResult, CodeStudioValidateResult } from "@/lib/api";
import {
  authoringGate,
  diagnosticsFor,
  liveBindGate,
  optionAGate,
  railSteps,
  testRunGate,
} from "./code-studio-gate";

const OK: CodeStudioValidateResult = { ok: true, syntax_ok: true, warnings: [], error: null, line: null };
const CODE = "for rec in records:\n    rec.write({'name': 'x'})";

function failedTest(): CodeStudioTestRunResult {
  return {
    ok: false,
    validation: OK,
    ran_for_real: true,
    record: { model: "res.partner", id: 1 },
    exception: "boom",
    field_diff: [],
    snapshot_id: "snap-1",
  };
}

describe("authoringGate", () => {
  it("is unchecked until Validate runs, and never offers live bind", () => {
    const gate = authoringGate(CODE, null);
    expect(gate.status).toBe("unchecked");
    expect(liveBindGate(gate, true, null, CODE)).toEqual({ ready: false, reason: "Validate this code first." });
    expect(optionAGate(gate).ready).toBe(false);
    expect(testRunGate(gate, true).ready).toBe(false);
  });

  it("passes only for the exact code that was validated", () => {
    const pinned = { code: CODE, result: OK };
    expect(authoringGate(CODE, pinned).status).toBe("passed");
    expect(liveBindGate(authoringGate(CODE, pinned), true, null, CODE).ready).toBe(true);
    const edited = `${CODE}\n`;
    const stale = authoringGate(edited, pinned);
    expect(stale.status).toBe("stale");
    expect(liveBindGate(stale, true, null, edited).reason).toBe("This code changed. Validate again.");
  });

  it("keeps live bind off for blocked rules but lets the Option A zip through", () => {
    const code = "import os\nrecords.write({})";
    const result = { ...OK, warnings: [{ code: "imports_forbidden", message: "Imports are blocked.", line: "1" }] };
    const gate = authoringGate(code, { code, result });
    expect(gate.status).toBe("blocked");
    expect(liveBindGate(gate, true, null, code).ready).toBe(false);
    expect(optionAGate(gate).ready).toBe(true);
  });

  it("treats a syntax error as a hard stop for every path", () => {
    const result = { ok: false, syntax_ok: false, warnings: [], error: "Syntax error: bad (line 2)", line: 2 };
    const gate = authoringGate(CODE, { code: CODE, result });
    expect(gate.status).toBe("syntax");
    expect(optionAGate(gate).ready).toBe(false);
    expect(diagnosticsFor(CODE, gate.validation)).toEqual([{ line: 2, message: "Syntax error: bad (line 2)" }]);
  });

  it("refuses bind without the probe and after a failed test on the same code", () => {
    const gate = authoringGate(CODE, { code: CODE, result: OK });
    expect(liveBindGate(gate, false, null, CODE).ready).toBe(false);
    expect(liveBindGate(gate, true, { code: CODE, result: failedTest() }, CODE).reason).toMatch(/test run failed/);
  });

  it("dedupes a local rule hit and the server warning on the same line", () => {
    const code = "import os";
    const result = { ...OK, warnings: [{ code: "imports_forbidden", message: "Imports are blocked.", line: "1" }] };
    expect(diagnosticsFor(code, result)).toHaveLength(1);
  });
});

describe("railSteps", () => {
  it("marks bind as next only once the gate passes", () => {
    const before = railSteps({ gate: authoringGate(CODE, null), path: "live", test: null, code: CODE, probeOk: true });
    expect(before.map((s) => [s.key, s.state])).toEqual([
      ["write", "done"],
      ["validate", "current"],
      ["test", "todo"],
      ["bind", "todo"],
    ]);
    const after = railSteps({
      gate: authoringGate(CODE, { code: CODE, result: OK }),
      path: "live",
      test: null,
      code: CODE,
      probeOk: true,
    });
    expect(after.find((s) => s.key === "bind")?.state).toBe("current");
  });

  it("says why bind is locked after a failed test", () => {
    const steps = railSteps({
      gate: authoringGate(CODE, { code: CODE, result: OK }),
      path: "live",
      test: { code: CODE, result: failedTest() },
      code: CODE,
      probeOk: true,
    });
    expect(steps.find((s) => s.key === "test")?.state).toBe("blocked");
    expect(steps.find((s) => s.key === "bind")?.detail).toBe("Locked: last test failed");
  });

  it("ends the Option A rail with a human sandbox and promote step", () => {
    const steps = railSteps({
      gate: authoringGate(CODE, { code: CODE, result: OK }),
      path: "option_a",
      test: null,
      code: CODE,
      probeOk: false,
    });
    expect(steps.map((s) => s.key)).toEqual(["write", "validate", "zip", "sandbox"]);
    expect(steps[3].detail).toMatch(/person/);
  });
});
