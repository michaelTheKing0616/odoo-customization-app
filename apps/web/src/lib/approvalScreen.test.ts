import { describe, expect, it } from "vitest";
import {
  PAGE_TITLE,
  PRIMARY_CTA,
  canDeployRule,
  defaultApprovalRuleForm,
  approvalsHonestyGuide,
  approvalsSessionBadge,
  engineChipLabel,
  sanitizeApprovalsCopy,
  entriesEmptyGuide,
  filterApprovalRules,
  parseUserId,
  processesEmptyGuide,
  ruleMetaLine,
  rulesEmptyGuide,
  approvalsErrorGuide,
  entryStatusVariant,
} from "./approvalScreen";
import type { ApprovalRule } from "@/lib/api";

const sample: ApprovalRule = {
  id: "r1",
  connection_id: "c1",
  engine: "community",
  name: "Confirm partner",
  target_model: "res.partner",
  button_method: "action_confirm",
  button_label: "Confirm",
  steps: [{ order: 1, approver_user_ids: [2] }],
  active: true,
  deployed: true,
};

describe("approvalScreen copy", () => {
  it("keeps the page distinct from the plan inbox", () => {
    expect(PAGE_TITLE).toBe("Odoo approval rules");
    expect(PRIMARY_CTA).toBe("Deploy a rule");
    expect(PAGE_TITLE.toLowerCase()).not.toContain("inbox");
  });

  it("blocks deploy until model, name, and button are set", () => {
    const form = defaultApprovalRuleForm();
    expect(canDeployRule(form)).toBe(false);
    form.buttonMethod = "action_confirm";
    expect(canDeployRule(form)).toBe(true);
    form.name = "   ";
    expect(canDeployRule(form)).toBe(false);
  });

  it("parses user ids with a safe fallback", () => {
    expect(parseUserId("7")).toBe(7);
    expect(parseUserId("")).toBe(2);
    expect(parseUserId("nope")).toBe(2);
  });

  it("filters rules by name, model, and button", () => {
    const rows = [
      sample,
      { ...sample, id: "r2", name: "Validate SO", target_model: "sale.order", button_method: "action_confirm" },
    ];
    expect(filterApprovalRules(rows, "partner")).toHaveLength(1);
    expect(filterApprovalRules(rows, "action_confirm")).toHaveLength(2);
    expect(filterApprovalRules(rows, "zzzz")).toHaveLength(0);
  });

  it("builds empty and error guides with what/why/next", () => {
    const empty = rulesEmptyGuide(false, "");
    expect(empty.title).toMatch(/No Odoo approval rules/);
    expect(empty.why.length).toBeGreaterThan(10);
    expect(empty.next.toLowerCase()).toContain("deploy");

    const filtered = rulesEmptyGuide(true, "xyz");
    expect(filtered.title).toContain("xyz");

    const entries = entriesEmptyGuide();
    expect(entries.title).toMatch(/No approval entries/);

    const types = processesEmptyGuide("types");
    expect(types.next.toLowerCase()).toContain("scaffold");

    const err = approvalsErrorGuide("deploy");
    expect(err.next).toContain("Deploy a rule");
  });

  it("labels engines and entry status without purple/orange words", () => {
    expect(engineChipLabel({ engine: "studio", studio_available: true, studio_verify_state: "ok", community_available: true, gating: {
      feature: "approvals",
      title: "",
      why: "",
      options: [],
      available: true,
      capability_key: "approvals",
      gating_choices: [],
    } })).toMatch(/Studio/);
    expect(engineChipLabel({ engine: "community", studio_available: false, studio_verify_state: "n/a", community_available: true, gating: {
      feature: "approvals",
      title: "",
      why: "",
      options: [],
      available: true,
      capability_key: "approvals",
      gating_choices: [],
    } })).toMatch(/Community/);
    expect(ruleMetaLine(sample)).toContain("res.partner.action_confirm");
    expect(entryStatusVariant("pending")).toBe("warning");
    expect(entryStatusVariant("approved")).toBe("success");
    expect(entryStatusVariant("rejected")).toBe("danger");
  });

  it("folds engine honesty for the studio bar", () => {
    const g = approvalsHonestyGuide(null);
    expect(g.title.length).toBeGreaterThan(2);
    expect(`${g.title}${g.why}${g.next}`).not.toMatch(/\u2014|\u2013/);
    expect(approvalsSessionBadge(null).label.length).toBeGreaterThan(2);
    expect(sanitizeApprovalsCopy("a — b")).toBe("a - b");
  });
});
