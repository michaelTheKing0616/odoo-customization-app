/**
 * UI-S-18 Code Studio authoring gate.
 *
 * Validate is the gate. Nothing that touches the database (test run, live bind)
 * and nothing that packages the code (Option A zip) is offered until the
 * current code has passed Validate. Any edit after Validate voids the pass.
 */
import type { CodeStudioTestRunResult, CodeStudioValidateResult } from "@/lib/api";

export type LineDiagnostic = {
  line: number;
  message: string;
};

export const LOCAL_RULES: { code: string; pattern: RegExp; message: string }[] = [
  {
    code: "imports_forbidden",
    pattern: /^\s*(?:import|from)\s+/,
    message: "imports_forbidden: Import statements are blocked in server-action safe_eval.",
  },
  {
    code: "sudo_pattern",
    pattern: /\b(?:\.sudo\s*\(|sudo\s*\()/,
    message: "sudo_pattern: sudo is blocked on the server-action path.",
  },
  {
    code: "unlink_pattern",
    pattern: /\b(?:\.unlink\s*\(|unlink\s*\()/,
    message: "unlink_pattern: unlink is blocked on the server-action path.",
  },
];

/** A validation or test result, pinned to the exact code it judged. */
export type Pinned<T> = { code: string; result: T };

export type AuthoringGateStatus = "empty" | "unchecked" | "stale" | "syntax" | "blocked" | "passed";

export type AuthoringGate = {
  status: AuthoringGateStatus;
  /** Validation for the code on screen. Null when unchecked or stale. */
  validation: CodeStudioValidateResult | null;
  /** Short status for chips and the editor bar. */
  label: string;
};

export type ActionGate = {
  ready: boolean;
  reason: string | null;
};

function lineFromMessage(message: string): number | null {
  const match = message.match(/line\s+(\d+)/i);
  if (!match) return null;
  const line = Number(match[1]);
  return Number.isFinite(line) ? line : null;
}

export function localRuleHits(code: string): LineDiagnostic[] {
  const found: LineDiagnostic[] = [];
  code.split("\n").forEach((line, index) => {
    for (const rule of LOCAL_RULES) {
      if (rule.pattern.test(line)) found.push({ line: index + 1, message: rule.message });
    }
  });
  return found;
}

export function diagnosticsFor(
  code: string,
  validation: CodeStudioValidateResult | null,
): LineDiagnostic[] {
  const found: LineDiagnostic[] = [];
  const seen = new Set<string>();
  function push(line: number, message: string) {
    const key = `${line}:${message.split(":")[0]}`;
    if (seen.has(key)) return;
    seen.add(key);
    found.push({ line, message });
  }
  for (const hit of localRuleHits(code)) push(hit.line, hit.message);
  if (validation && !validation.ok && validation.error) {
    const line = validation.line ?? lineFromMessage(validation.error);
    if (line) push(line, validation.error);
  }
  for (const warning of validation?.warnings ?? []) {
    const line = warning.line ? Number(warning.line) : null;
    if (line) push(line, `${warning.code}: ${warning.message}`);
  }
  return found;
}

export function authoringGate(
  code: string,
  pinned: Pinned<CodeStudioValidateResult> | null,
): AuthoringGate {
  if (code.trim() === "") return { status: "empty", validation: null, label: "No code yet" };
  if (!pinned) return { status: "unchecked", validation: null, label: "Not validated" };
  if (pinned.code !== code) return { status: "stale", validation: null, label: "Changed since Validate" };
  const v = pinned.result;
  if (!v.ok || !v.syntax_ok) return { status: "syntax", validation: v, label: "Syntax error" };
  if (v.warnings.length > 0 || localRuleHits(code).length > 0) {
    return { status: "blocked", validation: v, label: "Blocked rule" };
  }
  return { status: "passed", validation: v, label: "Validated" };
}

const GATE_REASON: Record<Exclude<AuthoringGateStatus, "passed">, string> = {
  empty: "Write code, then validate it.",
  unchecked: "Validate this code first.",
  stale: "This code changed. Validate again.",
  syntax: "Fix the syntax error, then validate again.",
  blocked: "Remove the blocked lines, then validate again.",
};

export function gateReason(status: AuthoringGateStatus): string | null {
  return status === "passed" ? null : GATE_REASON[status];
}

/** Test run executes the code on a real record, so it waits for the gate too. */
export function testRunGate(gate: AuthoringGate, probeOk: boolean): ActionGate {
  if (!probeOk) return { ready: false, reason: "The instance probe has not cleared live server actions." };
  const reason = gateReason(gate.status);
  return reason ? { ready: false, reason } : { ready: true, reason: null };
}

/** Live bind is the live install of authored code: never before the gate passes. */
export function liveBindGate(
  gate: AuthoringGate,
  probeOk: boolean,
  test: Pinned<CodeStudioTestRunResult> | null,
  code: string,
): ActionGate {
  if (!probeOk) return { ready: false, reason: "The instance probe has not cleared live server actions." };
  const reason = gateReason(gate.status);
  if (reason) return { ready: false, reason };
  if (test && test.code === code && !test.result.ok) {
    return { ready: false, reason: "The last test run failed. Bind stays off until a new pass." };
  }
  return { ready: true, reason: null };
}

/**
 * Option A packages the code into a module zip. Blocked server-action rules are
 * shown but do not stop the zip; a syntax error or unvalidated code does.
 */
export function optionAGate(gate: AuthoringGate): ActionGate {
  if (gate.status === "passed" || gate.status === "blocked") return { ready: true, reason: null };
  return { ready: false, reason: gateReason(gate.status) };
}

export type RailStepState = "done" | "current" | "blocked" | "todo" | "optional";

export type RailStep = { key: string; label: string; detail: string; state: RailStepState };

export function railSteps(input: {
  gate: AuthoringGate;
  path: "live" | "option_a";
  test: Pinned<CodeStudioTestRunResult> | null;
  code: string;
  probeOk: boolean;
}): RailStep[] {
  const { gate, path, test, code, probeOk } = input;
  const passed = gate.status === "passed";
  const currentTest = test && test.code === code ? test.result : null;
  const write: RailStep = {
    key: "write",
    label: "Write",
    detail: gate.status === "empty" ? "Server-action body" : `${code.split("\n").length} lines`,
    state: gate.status === "empty" ? "current" : "done",
  };
  const validate: RailStep = {
    key: "validate",
    label: "Validate",
    detail: gate.label,
    state:
      gate.status === "empty"
        ? "todo"
        : passed
          ? "done"
          : gate.status === "syntax" || gate.status === "blocked"
            ? "blocked"
            : "current",
  };
  if (path === "option_a") {
    const zipReady = optionAGate(gate).ready;
    return [
      write,
      validate,
      {
        key: "zip",
        label: "Download zip",
        detail: zipReady ? "Ready. Nothing installs here" : "Locked until Validate",
        state: zipReady ? "current" : "todo",
      },
      { key: "sandbox", label: "Sandbox, then publish", detail: "A person, outside this screen", state: "todo" },
    ];
  }
  const testStep: RailStep = {
    key: "test",
    label: "Test run",
    detail: currentTest ? (currentTest.ok ? "Passed on a record" : "Failed") : "Optional, on one record",
    state: currentTest ? (currentTest.ok ? "done" : "blocked") : passed ? "optional" : "todo",
  };
  const bindReady = liveBindGate(gate, probeOk, test, code).ready;
  const bindDetail = bindReady
    ? "Ready. Confirm phrase next"
    : !probeOk
      ? "Probe not cleared"
      : passed
        ? "Locked: last test failed"
        : "Locked until Validate";
  return [
    write,
    validate,
    testStep,
    {
      key: "bind",
      label: "Bind live",
      detail: bindDetail,
      state: bindReady ? "current" : "todo",
    },
  ];
}
