import { describe, expect, it } from "vitest";
import {
  WIZARD_ONLINE_HONESTY,
  applyBlockedReason,
  composeClarifiedPrompt,
  generateBlockedReason,
  providerSuffix,
  wizardErrorCopy,
  wizardPrimaryAction,
} from "./wizard-ui";

const EM_DASH = "\u2014";

describe("wizardPrimaryAction", () => {
  it("names exactly one primary per stage", () => {
    expect(wizardPrimaryAction({ hasDraft: false })).toBe("generate");
    expect(wizardPrimaryAction({ hasDraft: true })).toBe("apply");
    expect(wizardPrimaryAction({ hasDraft: true, moduleDelivery: true })).toBe("zip");
    expect(wizardPrimaryAction({ hasDraft: true, stockReuse: true })).toBe("job");
    expect(wizardPrimaryAction({ hasDraft: true, refuseClone: true })).toBe("none");
  });
});

describe("generateBlockedReason", () => {
  it("says what is missing, in order of what the user must do first", () => {
    expect(generateBlockedReason({ promptLength: 0 })).toMatch(/Describe what you need/);
    expect(generateBlockedReason({ promptLength: 40, overlapPending: true })).toMatch(
      /overlap finding/,
    );
    expect(
      generateBlockedReason({ promptLength: 40, needsConnectReview: true, connectApproved: false }),
    ).toMatch(/connect points/);
    expect(
      generateBlockedReason({ promptLength: 40, needsConnectReview: true, connectApproved: true }),
    ).toBeNull();
    expect(generateBlockedReason({ promptLength: 0, aiBusy: true })).toBeNull();
  });
});

describe("applyBlockedReason", () => {
  const ok = { hasDraft: true, canApply: true, finisherComplete: true };
  it("is null when Apply is allowed and honest when it is not", () => {
    expect(applyBlockedReason(ok)).toBeNull();
    expect(applyBlockedReason({ ...ok, finisherComplete: false })).toMatch(/quality pass/);
    expect(applyBlockedReason({ ...ok, stockReuse: true })).toMatch(/Job Autopilot/);
    expect(applyBlockedReason({ ...ok, refuseClone: true })).toMatch(/Apps Store clone/);
    expect(
      applyBlockedReason({ ...ok, canApply: false, generateUiBlocked: "Probe first" }),
    ).toBe("Probe first");
  });
});

describe("composeClarifiedPrompt", () => {
  it("appends the answer once and keeps the original brief", () => {
    const once = composeClarifiedPrompt("Track inspections", "Where?", "On project tasks");
    expect(once).toBe('Track inspections\n\nAnswer to "Where?": On project tasks');
    expect(composeClarifiedPrompt(once, "Where?", "On project tasks")).toBe(once);
    expect(composeClarifiedPrompt("Brief", "Where?", "  ")).toBe("Brief");
  });
});

describe("providerSuffix", () => {
  it("drops the generic AI label instead of printing (AI) twice", () => {
    expect(providerSuffix(true, "AI")).toBe("");
    expect(providerSuffix(true, "Ollama")).toBe(" with Ollama");
    expect(providerSuffix(false, "Ollama")).toBe(" with AI off");
  });
});

describe("wizardErrorCopy", () => {
  it("gives what, why, and next without blame", () => {
    const timeout = wizardErrorCopy({
      message: "The model provider did not answer within 120 seconds.",
      hasDraft: false,
    });
    expect(timeout.message).toMatch(/120 seconds/);
    expect(timeout.why).toMatch(/took too long/);
    expect(timeout.next).toMatch(/never writes to Odoo/);
    expect(timeout.next).toMatch(/template/);

    const withDraft = wizardErrorCopy({ message: "Sandbox validate failed", hasDraft: true });
    expect(withDraft.next).toMatch(/draft is still here/);
    expect(withDraft.why).toBeNull();

    const load = wizardErrorCopy({
      message: "Could not load connection (timeout or API down). Templates still available.",
      hasDraft: false,
    });
    expect(load.title).toBe("This connection did not load");
    expect(load.next).toMatch(/Templates still work/);
  });

  it("never blames the user or uses em dashes", () => {
    for (const copy of [
      wizardErrorCopy({ message: "x", hasDraft: false }),
      wizardErrorCopy({ message: "403 forbidden", hasDraft: true }),
    ]) {
      const text = `${copy.title} ${copy.why ?? ""} ${copy.next}`;
      expect(text).not.toMatch(/oops|you did|your fault|!/i);
      expect(text).not.toContain(EM_DASH);
    }
  });
});

describe("WIZARD_ONLINE_HONESTY", () => {
  it("never implies a live Python install on Odoo Online", () => {
    expect(WIZARD_ONLINE_HONESTY.body).toMatch(/cannot be installed on Online/);
    expect(WIZARD_ONLINE_HONESTY.body).not.toContain(EM_DASH);
  });
});
