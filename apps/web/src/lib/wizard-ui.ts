/**
 * Wizard (Draft Studio route) UI copy and action rules. Chrome only: no API calls,
 * no generator logic. Kept pure so the page and its tests share one source.
 */

export type WizardStage = "prompt" | "review";

export type WizardPrimaryAction = "generate" | "apply" | "zip" | "job" | "none";

/** Exactly one filled action per stage. */
export function wizardPrimaryAction(opts: {
  hasDraft: boolean;
  stockReuse?: boolean;
  refuseClone?: boolean;
  moduleDelivery?: boolean;
}): WizardPrimaryAction {
  if (!opts.hasDraft) return "generate";
  if (opts.refuseClone) return "none";
  if (opts.stockReuse) return "job";
  if (opts.moduleDelivery) return "zip";
  return "apply";
}

/** Why "Generate the draft" is disabled, in the reader's language. Null when it is enabled. */
export function generateBlockedReason(opts: {
  promptLength: number;
  aiBusy?: boolean;
  overlapPending?: boolean;
  needsConnectReview?: boolean;
  connectApproved?: boolean;
}): string | null {
  if (opts.aiBusy) return null;
  if (opts.promptLength < 3) return "Describe what you need in a sentence to enable this.";
  if (opts.overlapPending) {
    return "Choose Use, Extend, or Build anyway for each overlap finding first.";
  }
  if (opts.needsConnectReview && !opts.connectApproved) {
    return "Review and approve the connect points first.";
  }
  return null;
}

/** Why "Apply to Odoo" is disabled. Null when it is enabled. */
export function applyBlockedReason(opts: {
  hasDraft: boolean;
  busy?: boolean;
  canApply: boolean;
  finisherComplete: boolean;
  refuseClone?: boolean;
  stockReuse?: boolean;
  generateUiBlocked?: string | null;
}): string | null {
  if (!opts.hasDraft || opts.busy) return null;
  if (opts.refuseClone) {
    return "Nothing to apply. This brief asked for an Apps Store clone, which Ingenium does not build.";
  }
  if (opts.stockReuse) {
    return "Nothing to apply. Stock apps cover this brief, so Job Autopilot is the next step.";
  }
  if (!opts.finisherComplete) {
    return "Apply unlocks when the quality pass finishes and the scorecard appears.";
  }
  if (!opts.canApply) {
    return opts.generateUiBlocked || "This connection cannot take this draft yet.";
  }
  return null;
}

/** Prompt with the answer to the generator's one clarifying question appended once. */
export function composeClarifiedPrompt(prompt: string, question: string, answer: string): string {
  const base = prompt.trim();
  const a = answer.trim();
  if (!a) return base;
  const q = question.trim();
  const line = q ? `Answer to "${q}": ${a}` : `Answer: ${a}`;
  if (base.includes(line)) return base;
  return base ? `${base}\n\n${line}` : line;
}

/** "(Ollama)" style provider suffix; empty when the label is generic or AI is off. */
export function providerSuffix(aiEnabled: boolean, label: string | null | undefined): string {
  if (!aiEnabled) return " with AI off";
  const clean = String(label || "").trim();
  if (!clean || /^ai$/i.test(clean)) return "";
  return ` with ${clean}`;
}

export const WIZARD_ONLINE_HONESTY = {
  title: "Odoo Online connection",
  body:
    "Apply writes fields, views, and menus over RPC where Odoo Online allows it. " +
    "Custom Python modules cannot be installed on Online, so sandbox prove and Promote stay off here. " +
    "Download the module zip to install it on Odoo.sh or a self-hosted server.",
} as const;

export const WIZARD_ONLINE_PROMOTE_REASON =
  "Promote installs Python on this connection. Odoo Online does not allow custom modules.";

export const WIZARD_ONLINE_PROVE_REASON = "Sandbox prove is not available on Odoo Online";

export type WizardErrorCopy = {
  title: string;
  message: string;
  why: string | null;
  next: string;
};

/** Error block copy: what happened, why (when we can tell), and the next step. No blame. */
export function wizardErrorCopy(opts: {
  message: string;
  hasDraft: boolean;
}): WizardErrorCopy {
  const message = opts.message.trim() || "The server did not say what went wrong.";
  const m = message.toLowerCase();
  let why: string | null = null;
  if (/timed? ?out|timeout|did not answer|took too long|\b50[34]\b/.test(m)) {
    why = "The AI provider or the Odoo connection took too long to answer.";
  } else if (/failed to fetch|network|econn|unreachable|could not reach|offline/.test(m)) {
    why = "Ingenium could not reach its API or this Odoo connection.";
  } else if (/\b40[13]\b|permission|access denied|not allowed|forbidden/.test(m)) {
    why = "The Odoo user on this connection lacks the rights for that step.";
  }
  if (/could not load connection/.test(m)) {
    return {
      title: "This connection did not load",
      message,
      why: "The Ingenium API or this Odoo connection did not answer in time.",
      next: "Templates still work. Reload the page once the API is up, or check the connection on Connect.",
    };
  }
  if (!opts.hasDraft) {
    return {
      title: "The last step did not finish",
      message,
      why,
      next:
        "Generating a draft never writes to Odoo. Try Generate the draft again, or start from a ready-made template below.",
    };
  }
  return {
    title: "The last step did not finish",
    message,
    why,
    next: "Your draft is still here. Retry the step, or diagnose the message with the Expert.",
  };
}
