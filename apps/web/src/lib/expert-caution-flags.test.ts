import { describe, expect, it } from "vitest";
import {
  expertCautionDescription,
  expertCautionTone,
  formatExpertCautionFlag,
} from "./expert-caution-flags";

describe("formatExpertCautionFlag", () => {
  it("labels known flags for operators", () => {
    expect(formatExpertCautionFlag("legal_tax_deflection")).toBe("Not legal or tax advice");
    expect(formatExpertCautionFlag("low_retrieval")).toBe("Limited source matches");
    expect(formatExpertCautionFlag("access")).toBe("Access / ACL");
    expect(formatExpertCautionFlag("protected_:account.move")).toBe("Protected: account.move");
    expect(formatExpertCautionFlag("rule_based_view")).toBe("Guidance note");
  });

  it("humanizes unknown server flags instead of dropping them", () => {
    expect(formatExpertCautionFlag("custom_warning")).toBe("Custom Warning");
    expect(formatExpertCautionFlag("")).toBeNull();
  });

  it("elevates protected / PCM flags as danger", () => {
    expect(expertCautionTone("protected_:res.partner")).toBe("danger");
    expect(expertCautionTone("pcm_consistent_refusal")).toBe("danger");
    expect(expertCautionDescription("inferred_stack")).toMatch(/does not auto-install or auto-promote/);
  });
});
