/** Job Autopilot journey: chrome only, not the executor. */

export const JOB_AUTOPILOT_STAGES = [
  { id: "brief", label: "Brief" },
  { id: "run", label: "Run" },
  { id: "scorecard", label: "Scorecard" },
  { id: "promote", label: "Publish" },
] as const;

export type JobAutopilotJourneyId = (typeof JOB_AUTOPILOT_STAGES)[number]["id"];

export type JobAutopilotJourneyState = {
  id: JobAutopilotJourneyId;
  failed?: boolean;
  promoteReady?: boolean;
};

export const JOB_RUN_STEPS = [
  { id: "packet", label: "Packet" },
  { id: "stock", label: "Stock" },
  { id: "connectors", label: "Connectors" },
  { id: "custom", label: "Residual" },
  { id: "data", label: "Data" },
  { id: "smoke", label: "Smoke" },
] as const;

export type JobWriteMode = "observer" | "standard" | "production" | string;

export type JobAutopilotGate = {
  variant: "info" | "warning" | "danger";
  title: string;
  body: string;
  runBlocked: boolean;
  reason: "production" | "observer" | "staging" | "sandbox";
};

export type JobAutopilotBusy =
  | "packet"
  | "run"
  | "promote"
  | "pdf"
  | "fingerprint"
  | "dryrun"
  | "applypacket"
  | "settings"
  | null;

export function jobAutopilotJourneyFromState(opts: {
  busy?: string | null;
  hasPacket?: boolean;
  hasResult?: boolean;
  promoteReady?: boolean;
  refused?: boolean;
  failed?: boolean;
}): JobAutopilotJourneyState {
  const failed = Boolean(opts.failed || opts.refused);
  if (opts.busy === "run") return { id: "run", failed };
  if (failed && !opts.hasResult) return { id: "run", failed: true };
  if (opts.hasResult && opts.promoteReady) {
    return { id: "promote", promoteReady: true, failed };
  }
  if (opts.hasResult) return { id: "scorecard", failed };
  void opts.hasPacket;
  return { id: "brief" };
}

export function jobAutopilotJourneyHint(state: JobAutopilotJourneyState): string {
  if (state.failed && state.id === "run") {
    return "Autopilot did not finish. Fix the brief or run again on a sandbox. Publishing stays a step you confirm.";
  }
  switch (state.id) {
    case "brief":
      return "Describe the job. Plan summary is read-only. Autopilot writes a sandbox only. Completeness is not Cert.";
    case "run":
      return "Installing stock apps, residual x_* only, then RPC smoke. A complete draft is not the same as certified, and neither means Autopilot-ready. Publishing stays a step you confirm.";
    case "scorecard":
      return "Implementation-job scorecard is the Autopilot done-bar, not app plan 10.0. Review smoke, then hand off.";
    case "promote":
      return "Publishing stays a step you confirm. Autopilot never writes production. Download the report, or apply the config summary on a target.";
  }
}

export function jobAutopilotGate(opts: {
  writeMode?: JobWriteMode | null;
  sandbox?: boolean;
  localSandboxUrl?: boolean;
}): JobAutopilotGate {
  const mode = (opts.writeMode || "standard").toLowerCase();
  if (mode === "production") {
    return {
      variant: "danger",
      title: "Production refused",
      body:
        "Job Autopilot refuses write_mode=production. Clone a sandbox, run Autopilot there, then publish with a human confirm. A complete draft is not the same as certified, and neither means Autopilot-ready.",
      runBlocked: true,
      reason: "production",
    };
  }
  if (mode === "observer") {
    return {
      variant: "warning",
      title: "Observer cannot run Autopilot",
      body:
        "Observer connections cannot install modules or apply metadata. Switch write_mode to standard on a sandbox.",
      runBlocked: true,
      reason: "observer",
    };
  }
  if (opts.sandbox || opts.localSandboxUrl) {
    return {
      variant: "info",
      title: "Sandbox-only delivery",
      body:
        "Stock Community apps first. Custom x_* is residual only. Done-bar is RPC process smoke on this sandbox, not app plan completeness. Publishing stays a step you confirm.",
      runBlocked: false,
      reason: "sandbox",
    };
  }
  return {
    variant: "warning",
    title: "Not an unattended sandbox",
    body:
      "This connection is not a local sandbox. Run will ask for confirm. Production Autopilot stays refused. Publishing stays a separate step you confirm.",
    runBlocked: false,
    reason: "staging",
  };
}

export function jobRunBlocked(writeMode?: JobWriteMode | null): boolean {
  const mode = (writeMode || "").toLowerCase();
  return mode === "production" || mode === "observer";
}

export function jobRunStepDone(stages: string[] | undefined, id: string): boolean {
  if (!stages?.length) return false;
  if (id === "custom") return stages.includes("custom") || stages.includes("custom_retry");
  return stages.includes(id);
}

export function jobScorecardHeadline(opts: {
  overall?: number;
  smokeOk?: boolean | null;
  promoteReady?: boolean;
}): string {
  if (typeof opts.overall !== "number") {
    return opts.smokeOk === true ? "Process smoke passed" : "Implementation-job scorecard";
  }
  const smoke =
    opts.smokeOk === true ? " · smoke passed" : opts.smokeOk === false ? " · smoke failed" : "";
  const promote = opts.promoteReady ? " · ready for human promote" : "";
  return `Job scorecard: ${opts.overall.toFixed(1)}/10${smoke}${promote}`;
}

export function jobScorecardBody(opts: {
  smokeOk?: boolean | null;
  promoteReady?: boolean;
  stockOnly?: boolean;
  hasFindings?: boolean;
}): string | null {
  if (opts.hasFindings) return null;
  if (opts.stockOnly && opts.smokeOk) {
    return "Built-in apps only job. A complete draft is not the same as certified, and neither means Autopilot-ready. This sandbox is the delivery. Publishing stays a step you confirm.";
  }
  if (opts.smokeOk && opts.promoteReady) {
    return "RPC smoke passed. Implementation-job score is not app plan 10.0. Publishing stays a step you confirm.";
  }
  if (opts.smokeOk === false) {
    return "Smoke did not pass. Do not promote. Completeness 10.0 is not this bar.";
  }
  return "Implementation-job scorecard is separate from Completeness and Certification.";
}

export function residualZipBase64(result: {
  custom?: {
    zip_base64?: string | null;
    elite?: unknown;
  } | null;
} | null): string | null {
  const direct = result?.custom?.zip_base64;
  if (direct) return direct;
  const elite = result?.custom?.elite;
  if (elite && typeof elite === "object" && typeof (elite as { zip_base64?: string }).zip_base64 === "string") {
    return (elite as { zip_base64: string }).zip_base64;
  }
  return null;
}

export function hasResidualModuleSpec(result: {
  custom?: { spec?: Record<string, unknown> | null } | null;
} | null): boolean {
  const spec = result?.custom?.spec;
  return Boolean(spec && typeof spec === "object" && Object.keys(spec).length);
}

export function deliveryReportMarkdown(result: {
  report_markdown?: string | null;
  scorecard_note?: string;
  ok?: boolean;
  job_scorecard?: { overall?: number } | null;
  promote_ready?: boolean;
  message?: string;
}): string {
  if (result.report_markdown) return result.report_markdown;
  return [
    "# Job Autopilot UAT report",
    "",
    result.scorecard_note,
    "",
    `Status: ${result.ok ? "smoke passed" : "not ready"}`,
    `Job scorecard overall: ${result.job_scorecard?.overall ?? "n/a"}/10`,
    `Promote ready: ${result.promote_ready ? "yes (human step)" : "no"}`,
    "",
    result.message,
  ].join("\n");
}

export function jobAutopilotErrorTitle(message: string | null | undefined): string {
  const text = (message || "").trim();
  if (!text) return "Job Autopilot request failed";
  if (/production/i.test(text)) return "Production refused";
  if (/observer/i.test(text)) return "Observer cannot run Autopilot";
  if (/packet|plan/i.test(text)) return "Packet planning failed";
  if (/promot/i.test(text)) return "Publish failed";
  if (/smoke/i.test(text)) return "Process smoke failed";
  if (/sandbox|install/i.test(text)) return "Sandbox run failed";
  return "Job Autopilot request failed";
}

export function jobProgressLabel(opts: {
  busy?: string | null;
  stepLabel?: string | null;
  elapsedMinutes?: number;
}): string {
  const minutes =
    typeof opts.elapsedMinutes === "number" && opts.elapsedMinutes > 0
      ? ` (${opts.elapsedMinutes} min)`
      : "";
  if (opts.stepLabel) return `Autopilot: ${opts.stepLabel}${minutes}`;
  switch (opts.busy) {
    case "run":
      return `Running Autopilot${minutes}`;
    case "packet":
      return "Planning packet";
    case "promote":
      return "Promoting to target";
    case "pdf":
      return "Building PDF";
    case "fingerprint":
      return "Fingerprinting target";
    case "dryrun":
      return "Test-running the packet";
    case "applypacket":
      return "Applying config summary";
    case "settings":
      return "Capturing settings";
    default:
      return "Working";
  }
}

export function sandboxOpenLabel(result: {
  smoke?: { invoice_id?: number | null; sale_order_id?: number | null } | null;
  custom?: { root_menu_id?: number | null } | null;
} | null): string {
  if (result?.smoke?.invoice_id) return "Open smoke invoice";
  if (result?.smoke?.sale_order_id) return "Open smoke quotation";
  if (result?.custom?.root_menu_id) return "Open sandbox app";
  return "Open sandbox";
}

export function jobAutopilotHeaderDescription(
  connectionName?: string,
  writeMode?: JobWriteMode | null,
): string {
  const mode = (writeMode || "").toLowerCase();
  if (mode === "production") {
    return connectionName
      ? `${connectionName} · Autopilot refuses production. Run on a sandbox.`
      : "Autopilot refuses production. Clone a sandbox, then publish.";
  }
  if (mode === "observer") {
    return connectionName
      ? `${connectionName} · observer cannot run Autopilot`
      : "Observer cannot install or apply. Use a sandbox.";
  }
  if (connectionName) {
    return `${connectionName} · sandbox-only: stock first, residual x_*, human promote`;
  }
  return "Plan a sandbox job. Run built-in apps first install and RPC smoke. Publishing stays a step you confirm.";
}

export function jobAutopilotProductionRefuseMessage(): string {
  return "Autopilot refuses write_mode=production. Clone a sandbox, run Autopilot there, then publish.";
}

export function jobAutopilotObserverRefuseMessage(): string {
  return "Observer connections cannot install or apply. Switch write_mode to standard on a sandbox.";
}


/** Connector recipe order (UI-S-22 stepper). Matches backend CONNECTOR_ORDER. */
export const JOB_CONNECTOR_RECIPE = [
  { id: "payments", label: "Payments" },
  { id: "inbound_orders", label: "Inbound orders" },
  { id: "messaging", label: "Messaging" },
  { id: "hardware", label: "Hardware" },
  { id: "statutory_payroll", label: "Statutory" },
] as const;

export type JobConnectorRecipeId = (typeof JOB_CONNECTOR_RECIPE)[number]["id"];

export function jobConnectorRecipeSteps(detected?: string[] | null): Array<{
  id: string;
  label: string;
  active: boolean;
}> {
  const set = new Set((detected || []).map((id) => id.toLowerCase()));
  return JOB_CONNECTOR_RECIPE.map((row) => ({
    id: row.id,
    label: row.label,
    active: set.has(row.id),
  }));
}

export function jobConnectorStepState(
  id: string,
  connectors?: {
    ran?: string[];
    failed?: string[];
    skipped_ids?: string[];
    steps?: Array<{ name: string; ok: boolean }>;
  } | null,
): "done" | "failed" | "skipped" | "queued" | "idle" {
  if (!connectors) return "idle";
  const ran = new Set((connectors.ran || []).map((x) => x.toLowerCase()));
  const failed = new Set((connectors.failed || []).map((x) => x.toLowerCase()));
  const skipped = new Set((connectors.skipped_ids || []).map((x) => x.toLowerCase()));
  const key = id.toLowerCase();
  if (failed.has(key)) return "failed";
  if (ran.has(key)) return "done";
  if (skipped.has(key)) return "skipped";
  const probe = (connectors.steps || []).find((s) => s.name.toLowerCase().includes(key.replace(/_/g, " ")) || s.name.toLowerCase() === key);
  if (probe) return probe.ok ? "done" : "failed";
  return "queued";
}

export function jobAutopilotOnlineHonesty(): { title: string; body: string } {
  return {
    title: "Odoo Online: no live Python install",
    body:
      "Autopilot never installs custom Python modules on Odoo Online. Plan the packet here, run stock bootstrap and RPC smoke on a sandbox (Community or Odoo.sh), then Publishing stays a step you confirm. Metadata and config summary replay are the Online path.",
  };
}

export type JobAutopilotErrorGuide = {
  what: string;
  why: string;
  next: string;
};

export function jobAutopilotErrorGuide(message: string | null | undefined): JobAutopilotErrorGuide | null {
  const text = (message || "").trim();
  if (!text) return null;
  if (/production/i.test(text)) {
    return {
      what: "Autopilot refused this connection.",
      why: "write_mode=production is never a write target for Autopilot.",
      next: "Clone or connect a sandbox, run Autopilot there, then use you publish.",
    };
  }
  if (/observer/i.test(text)) {
    return {
      what: "Observer cannot run Autopilot.",
      why: "Observer mode cannot install modules or apply metadata.",
      next: "Switch write_mode to standard on a sandbox, then Run Autopilot.",
    };
  }
  if (/online|saas|python/i.test(text)) {
    return {
      what: "This host cannot take a live Python module install.",
      why: "Odoo Online blocks custom Python module install from Ingenium.",
      next: "Use a Community sandbox or Odoo.sh for Autopilot install and smoke.",
    };
  }
  if (/promot/i.test(text)) {
    return {
      what: "Promote did not finish.",
      why: "Promote is a separate human step onto another connection.",
      next: "Confirm the target connection, type the confirm phrase, and try again.",
    };
  }
  if (/smoke/i.test(text)) {
    return {
      what: "Process smoke failed.",
      why: "The named RPC process did not pass on this sandbox.",
      next: "Read the smoke steps, fix the brief or stock apps, then Run Autopilot again. Do not promote.",
    };
  }
  if (/packet|plan/i.test(text)) {
    return {
      what: "Packet planning failed.",
      why: "The brief or files could not build a built-in apps first plan.",
      next: "Tighten the brief (who, what, country), attach CSV/XLSX if needed, then Plan summary again.",
    };
  }
  return {
    what: "Job Autopilot request failed.",
    why: text.slice(0, 160),
    next: "Fix the brief or connection, then Plan summary or Run Autopilot on a sandbox.",
  };
}

export function isStockOnlyPacket(packet: {
  custom_residuals?: Array<unknown>;
} | null): boolean {
  return Boolean(packet && !packet.custom_residuals?.length);
}

export function jobRunStepCurrent(
  stages: string[] | undefined,
  busy: string | null | undefined,
): string | null {
  if (busy !== "run") return null;
  const pending = JOB_RUN_STEPS.find((step) => !jobRunStepDone(stages, step.id));
  return pending?.id ?? "smoke";
}
