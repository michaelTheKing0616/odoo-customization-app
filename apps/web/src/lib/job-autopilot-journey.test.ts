import { describe, expect, it } from "vitest";
import {
  deliveryReportMarkdown,
  hasResidualModuleSpec,
  isStockOnlyPacket,
  jobAutopilotErrorTitle,
  jobAutopilotGate,
  jobAutopilotHeaderDescription,
  jobAutopilotJourneyFromState,
  jobAutopilotJourneyHint,
  jobAutopilotObserverRefuseMessage,
  jobAutopilotProductionRefuseMessage,
  jobProgressLabel,
  jobRunBlocked,
  jobRunStepCurrent,
  jobRunStepDone,
  jobScorecardBody,
  jobScorecardHeadline,
  residualZipBase64,
  sandboxOpenLabel,
} from "./job-autopilot-journey";

describe("jobAutopilotJourneyFromState", () => {
  it("maps brief → run → scorecard → promote without mixing Draft Studio ids", () => {
    expect(jobAutopilotJourneyFromState({}).id).toBe("brief");
    expect(jobAutopilotJourneyFromState({ hasPacket: true }).id).toBe("brief");
    expect(jobAutopilotJourneyFromState({ busy: "run" }).id).toBe("run");
    expect(jobAutopilotJourneyFromState({ hasResult: true }).id).toBe("scorecard");
    expect(
      jobAutopilotJourneyFromState({ hasResult: true, promoteReady: true }),
    ).toEqual({
      id: "promote",
      promoteReady: true,
      failed: false,
    });
    expect(jobAutopilotJourneyFromState({ busy: "run", hasResult: true }).id).toBe("run");
  });

  it("marks run failed when Autopilot dies before a result exists", () => {
    expect(jobAutopilotJourneyFromState({ failed: true })).toEqual({
      id: "run",
      failed: true,
    });
    expect(jobAutopilotJourneyFromState({ refused: true })).toEqual({
      id: "run",
      failed: true,
    });
  });
});

describe("jobAutopilotJourneyHint", () => {
  it("keeps Completeness / Cert / Autopilot honesty and human promote", () => {
    expect(jobAutopilotJourneyHint({ id: "brief" })).toMatch(/sandbox only/i);
    expect(jobAutopilotJourneyHint({ id: "brief" })).toMatch(/Completeness is not Cert/i);
    expect(jobAutopilotJourneyHint({ id: "run" })).toMatch(/Completeness ≠ Cert ≠ Autopilot/);
    expect(jobAutopilotJourneyHint({ id: "run" })).toMatch(/Promote stays human/);
    expect(jobAutopilotJourneyHint({ id: "scorecard" })).toMatch(/not ModuleSpec 10\.0/);
    expect(jobAutopilotJourneyHint({ id: "promote" })).toMatch(/never writes production/);
    expect(jobAutopilotJourneyHint({ id: "run", failed: true })).toMatch(/Promote stays human/);
  });
});

describe("jobAutopilotGate", () => {
  it("refuses production and observer without weakening the sandbox gate", () => {
    const production = jobAutopilotGate({ writeMode: "production" });
    expect(production.runBlocked).toBe(true);
    expect(production.reason).toBe("production");
    expect(production.variant).toBe("danger");
    expect(production.body).toMatch(/refuses write_mode=production/);
    expect(production.body).toMatch(/Completeness ≠ Cert ≠ Autopilot/);

    const observer = jobAutopilotGate({ writeMode: "observer" });
    expect(observer.runBlocked).toBe(true);
    expect(observer.reason).toBe("observer");
    expect(observer.body).toMatch(/cannot install/);

    expect(jobRunBlocked("production")).toBe(true);
    expect(jobRunBlocked("observer")).toBe(true);
    expect(jobRunBlocked("standard")).toBe(false);
  });

  it("marks local sandbox as the intended unattended path", () => {
    const sandbox = jobAutopilotGate({
      writeMode: "standard",
      sandbox: true,
      localSandboxUrl: true,
    });
    expect(sandbox.runBlocked).toBe(false);
    expect(sandbox.reason).toBe("sandbox");
    expect(sandbox.body).toMatch(/RPC process smoke/);
    expect(sandbox.body).not.toMatch(/!/);

    const staging = jobAutopilotGate({ writeMode: "standard" });
    expect(staging.reason).toBe("staging");
    expect(staging.variant).toBe("warning");
    expect(staging.runBlocked).toBe(false);
    expect(staging.body).toMatch(/will ask for confirm/);
  });
});

describe("jobScorecardHeadline", () => {
  it("never fuses Completeness with Certification or Autopilot", () => {
    expect(
      jobScorecardHeadline({ overall: 8.4, smokeOk: true, promoteReady: true }),
    ).toBe("Job scorecard: 8.4/10 · smoke passed · ready for human promote");
    expect(jobScorecardHeadline({ overall: 10, smokeOk: false })).toMatch(/smoke failed/);
    expect(jobScorecardHeadline({ overall: 10 })).not.toMatch(/Completeness/);
    expect(jobScorecardHeadline({ overall: 10 })).not.toMatch(/Cert/);
  });
});

describe("jobScorecardBody", () => {
  it("keeps stock-only and failed-smoke honesty", () => {
    expect(jobScorecardBody({ stockOnly: true, smokeOk: true })).toMatch(
      /Completeness ≠ Cert ≠ Autopilot/,
    );
    expect(jobScorecardBody({ smokeOk: false })).toMatch(/Do not promote/);
    expect(jobScorecardBody({ smokeOk: true, promoteReady: true })).toMatch(/Promote stays human/);
    expect(jobScorecardBody({ hasFindings: true })).toBeNull();
  });
});

describe("run ledger helpers", () => {
  it("treats custom_retry as residual done and names the current step", () => {
    expect(jobRunStepDone(["packet", "stock", "custom_retry"], "custom")).toBe(true);
    expect(jobRunStepDone(["packet"], "smoke")).toBe(false);
    expect(jobRunStepCurrent(["packet", "stock"], "run")).toBe("connectors");
    expect(jobRunStepCurrent(["packet"], "packet")).toBeNull();
  });
});

describe("delivery helpers", () => {
  it("reads residual zip, stock-only packet, and sandbox open labels", () => {
    expect(residualZipBase64({ custom: { zip_base64: "abc" } })).toBe("abc");
    expect(
      residualZipBase64({ custom: { elite: { zip_base64: "elite-zip" } } }),
    ).toBe("elite-zip");
    expect(residualZipBase64({ custom: { elite: {} } })).toBeNull();
    expect(isStockOnlyPacket({ custom_residuals: [] })).toBe(true);
    expect(isStockOnlyPacket({ custom_residuals: [{ key: "x" }] })).toBe(false);
    expect(hasResidualModuleSpec({ custom: { spec: { models: [] } } })).toBe(true);
    expect(hasResidualModuleSpec({ custom: { spec: {} } })).toBe(false);
    expect(sandboxOpenLabel({ smoke: { invoice_id: 9 } })).toBe("Open smoke invoice");
    expect(sandboxOpenLabel({ smoke: { sale_order_id: 3 } })).toBe("Open smoke quotation");
    expect(sandboxOpenLabel({ custom: { root_menu_id: 12 } })).toBe("Open sandbox app");
    expect(sandboxOpenLabel(null)).toBe("Open sandbox");
  });

  it("builds a UAT report without treating scorecard as go-live", () => {
    const md = deliveryReportMarkdown({
      ok: true,
      promote_ready: true,
      scorecard_note: "Completeness is not this bar",
      job_scorecard: { overall: 9.1 },
      message: "Smoke passed",
    });
    expect(md).toMatch(/smoke passed/);
    expect(md).toMatch(/yes \(human step\)/);
    expect(md).toMatch(/9\.1/);
    expect(deliveryReportMarkdown({ report_markdown: "# Ready" })).toBe("# Ready");
  });
});

describe("jobProgressLabel", () => {
  it("prefers the live step label and stays verb-first", () => {
    expect(jobProgressLabel({ busy: "run", stepLabel: "stock", elapsedMinutes: 4 })).toBe(
      "Autopilot: stock (4 min)",
    );
    expect(jobProgressLabel({ busy: "packet" })).toBe("Planning packet");
    expect(jobProgressLabel({ busy: "run" })).toBe("Running Autopilot");
  });
});

describe("copy helpers", () => {
  it("names the failed step and keeps header copy calm", () => {
    expect(jobAutopilotErrorTitle("write_mode=production refused")).toBe("Production refused");
    expect(jobAutopilotErrorTitle("Observer cannot install")).toBe(
      "Observer cannot run Autopilot",
    );
    expect(jobAutopilotErrorTitle("")).toBe("Job Autopilot request failed");
    expect(jobAutopilotHeaderDescription("Lab 19")).toMatch(/Lab 19/);
    expect(jobAutopilotHeaderDescription()).toMatch(/Promote stays human/);
    expect(jobAutopilotProductionRefuseMessage()).toMatch(/refuses write_mode=production/);
    expect(jobAutopilotObserverRefuseMessage()).toMatch(/Observer/);
  });
});
