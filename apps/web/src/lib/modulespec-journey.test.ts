import { describe, expect, it } from "vitest";
import {
  completenessNote,
  hasModuleSpecContent,
  localReadiness,
  moduleSpecErrorTitle,
  moduleSpecHeaderDescription,
  moduleSpecJourneyFromState,
  moduleSpecJourneyHint,
  moduleSpecSessionState,
  moduleSpecSummary,
  primaryDesignerModel,
  relationalFields,
} from "./modulespec-journey";
import { cloneModuleSpec, emptyModuleSpec } from "./modulespec-types";

const sampleSpec = {
  technical_name: "visitor_log",
  display_name: "Visitor log",
  depends: ["base"],
  models: [
    {
      model: "x_visitor_log",
      description: "Visitor log",
      fields: [
        { name: "x_name", ttype: "char", string: "Name", required: true },
        { name: "x_partner_id", ttype: "many2one", string: "Guest", relation: "res.partner" },
      ],
    },
  ],
  views: [{ name: "x_visitor_log.form", model: "x_visitor_log", type: "form", arch: "<form/>" }],
  menus: [{ name: "Visitor log", technical_name: "menu_x_visitor_log" }],
  access_rules: [{ name: "Visitor user", model: "model_x_visitor_log", perm_read: 1 }],
};

describe("moduleSpecJourneyFromState", () => {
  it("maps load → edit → validate → apply without mixing Draft Studio ids", () => {
    expect(moduleSpecJourneyFromState({}).id).toBe("load");
    expect(moduleSpecJourneyFromState({ hasContent: true }).id).toBe("edit");
    expect(moduleSpecJourneyFromState({ busy: "validate" }).id).toBe("validate");
    expect(moduleSpecJourneyFromState({ hasLiveValidation: true }).id).toBe("validate");
    expect(moduleSpecJourneyFromState({ applied: true })).toEqual({
      id: "apply",
      applied: true,
      failed: false,
    });
    expect(moduleSpecJourneyFromState({ busy: "apply", hasContent: true }).id).toBe("apply");
  });

  it("keeps validate current when live checks fail", () => {
    expect(moduleSpecJourneyFromState({ failed: true, hasContent: true })).toEqual({
      id: "validate",
      failed: true,
    });
  });
});

describe("moduleSpecJourneyHint", () => {
  it("keeps Completeness / Cert / Autopilot honesty and human promote", () => {
    expect(moduleSpecJourneyHint({ id: "load" })).toMatch(/hygiene/);
    expect(moduleSpecJourneyHint({ id: "edit" })).toMatch(/escape hatch/);
    expect(moduleSpecJourneyHint({ id: "edit" })).toMatch(/Completeness ≠ Cert ≠ Autopilot/);
    expect(moduleSpecJourneyHint({ id: "validate" })).toMatch(/not Certification/);
    expect(moduleSpecJourneyHint({ id: "validate" })).toMatch(/Promote stays human/);
    expect(moduleSpecJourneyHint({ id: "apply" })).toMatch(/Promote stays human/);
    expect(moduleSpecJourneyHint({ id: "validate", failed: true })).toMatch(/Promote stays human/);
  });
});

describe("moduleSpecSessionState", () => {
  it("uses draft / unsaved / saved like other premium composers", () => {
    expect(moduleSpecSessionState({ dirty: false, savedOnce: false })).toBe("draft");
    expect(moduleSpecSessionState({ dirty: true, savedOnce: false })).toBe("unsaved");
    expect(moduleSpecSessionState({ dirty: true, savedOnce: true })).toBe("unsaved");
    expect(moduleSpecSessionState({ dirty: false, savedOnce: true })).toBe("saved");
    expect(moduleSpecSessionState({ dirty: false, savedOnce: false, applied: true })).toBe("saved");
  });
});

describe("localReadiness", () => {
  it("blocks empty specs and missing relation targets", () => {
    const empty = localReadiness(emptyModuleSpec());
    expect(empty.applyBlocked).toBe(true);
    expect(empty.items.find((row) => row.id === "models")?.status).toBe("fail");

    const broken = localReadiness({
      ...sampleSpec,
      models: [
        {
          model: "x_visitor_log",
          fields: [{ name: "x_host_id", ttype: "many2one", string: "Host" }],
        },
      ],
    });
    expect(broken.applyBlocked).toBe(true);
    expect(broken.items.find((row) => row.id === "relations")?.status).toBe("fail");
  });

  it("treats stock reuse empty models as skip, not Generate UI ready", () => {
    const report = localReadiness({
      technical_name: "stock_reuse",
      display_name: "Stock coverage",
      models: [],
      _generation_engine: { capability: "stock_reuse" },
    });
    expect(report.applyBlocked).toBe(true);
    expect(report.items.find((row) => row.id === "models")?.status).toBe("skip");
    expect(report.headline).toMatch(/Stock reuse/);
    expect(report.body).toMatch(/Job Autopilot/);
    expect(report.body).toMatch(/Completeness ≠ Cert ≠ Autopilot/);
  });

  it("passes a filled visitor spec with honest warnings only when slices are missing", () => {
    const report = localReadiness(sampleSpec);
    expect(report.applyBlocked).toBe(false);
    expect(report.failCount).toBe(0);
    expect(report.items.find((row) => row.id === "models")?.status).toBe("pass");
    expect(report.headline).toMatch(/Ready to validate/);
    expect(report.body).toMatch(/Promote stays human/);
  });
});

describe("helpers", () => {
  it("summarizes, clones, and picks the first custom model for Designer", () => {
    const summary = moduleSpecSummary(sampleSpec);
    expect(summary).toEqual({
      models: 1,
      fields: 2,
      views: 1,
      menus: 1,
      access: 1,
      smart: 0,
      autos: 0,
      customCode: 0,
    });
    expect(hasModuleSpecContent(emptyModuleSpec())).toBe(false);
    expect(hasModuleSpecContent(sampleSpec)).toBe(true);
    expect(primaryDesignerModel(sampleSpec)).toBe("x_visitor_log");
    expect(relationalFields(sampleSpec)).toHaveLength(1);
    const clone = cloneModuleSpec(sampleSpec);
    clone.display_name = "Changed";
    expect(sampleSpec.display_name).toBe("Visitor log");
  });

  it("labels errors and completeness without fusing Cert", () => {
    expect(moduleSpecErrorTitle("Lint found issues in custom code blocks.")).toBe("Lint found issues");
    expect(moduleSpecErrorTitle("Generate UI failed")).toBe("Generate UI failed");
    expect(moduleSpecHeaderDescription("Lab 19")).toMatch(/Lab 19/);
    expect(
      completenessNote({
        ...sampleSpec,
        _scorecard: { score_0_10: 10 },
        _certification: { tier: "ReviewRequired" },
      }),
    ).toMatch(/hygiene/);
    expect(
      completenessNote({
        ...sampleSpec,
        _scorecard: { score_0_10: 10 },
        _certification: { tier: "ReviewRequired" },
      }),
    ).toMatch(/ReviewRequired/);
  });
});
