import { describe, expect, it } from "vitest";
import type { AccessRightRow, RecordRuleRow } from "@/lib/api";
import {
  accessFormFromRow,
  builderHref,
  composerSessionState,
  crudLetters,
  defaultAccessForm,
  defaultRuleForm,
  designerHref,
  isComposerDirty,
  isGlobalAccess,
  isGlobalRule,
  LIVE_PACK_RISKS,
  menusHref,
  parseModelList,
  ruleFormFromRow,
} from "./accessForm";

describe("composerSessionState", () => {
  it("maps dirty / savedOnce to chrome states", () => {
    expect(composerSessionState({ dirty: true, savedOnce: false })).toBe("unsaved");
    expect(composerSessionState({ dirty: false, savedOnce: true })).toBe("saved");
    expect(composerSessionState({ dirty: false, savedOnce: false })).toBe("draft");
  });
});

describe("isComposerDirty", () => {
  it("detects form vs baseline", () => {
    const a = defaultAccessForm();
    const b = defaultAccessForm();
    expect(isComposerDirty(a, b)).toBe(false);
    b.name = "Partner user";
    expect(isComposerDirty(a, b)).toBe(true);
  });
});

describe("crudLetters", () => {
  it("renders RWCD compact grants", () => {
    expect(crudLetters(defaultAccessForm())).toBe("RWC");
    expect(
      crudLetters({
        perm_read: false,
        perm_write: false,
        perm_create: false,
        perm_unlink: false,
      }),
    ).toBe("—");
    expect(crudLetters(defaultRuleForm())).toBe("RWCD");
  });
});

describe("live pack confirm", () => {
  it("names the global ir.rule risk in the confirm list", () => {
    expect(LIVE_PACK_RISKS.join(" ")).toMatch(/global ir\.rule/);
    expect(LIVE_PACK_RISKS.join(" ")).not.toMatch(/!/);
  });
});

describe("global grants", () => {
  it("treats empty group as global ACL / rule", () => {
    expect(isGlobalAccess("")).toBe(true);
    expect(isGlobalAccess("12")).toBe(false);
    expect(isGlobalAccess(null)).toBe(true);
    expect(isGlobalRule([])).toBe(true);
    expect(isGlobalRule([5])).toBe(false);
  });
});

describe("row round-trip", () => {
  it("loads ACL and rule rows into composer forms", () => {
    const access: AccessRightRow = {
      id: 1,
      name: "Partner user",
      model: "res.partner",
      model_id: 8,
      group_id: 4,
      group_name: "Internal User",
      perm_read: true,
      perm_write: false,
      perm_create: false,
      perm_unlink: false,
      active: true,
    };
    expect(accessFormFromRow(access)).toEqual({
      name: "Partner user",
      group_id: "4",
      perm_read: true,
      perm_write: false,
      perm_create: false,
      perm_unlink: false,
    });
    const rule: RecordRuleRow = {
      id: 2,
      name: "Own records",
      model: "res.partner",
      model_id: 8,
      domain_force: "[('create_uid', '=', user.id)]",
      group_ids: [4],
      perm_read: true,
      perm_write: true,
      perm_create: true,
      perm_unlink: true,
      active: true,
      global: false,
    };
    expect(ruleFormFromRow(rule).group_ids).toEqual([4]);
    expect(ruleFormFromRow(rule).domain_force).toContain("create_uid");
  });
});

describe("parseModelList", () => {
  it("splits comma-separated technical names", () => {
    expect(parseModelList(" res.partner, x_ticket , ")).toEqual(["res.partner", "x_ticket"]);
  });
});

describe("hrefs", () => {
  it("encodes model query for Designer, Builder, and Menus", () => {
    expect(designerHref("c1", "res.partner")).toBe(
      "/connections/c1/designer?model=res.partner",
    );
    expect(builderHref("c1", "x_ticket")).toBe("/connections/c1/builder?model=x_ticket");
    expect(menusHref("c1", "res.partner")).toBe("/connections/c1/menus?model=res.partner");
  });
});
