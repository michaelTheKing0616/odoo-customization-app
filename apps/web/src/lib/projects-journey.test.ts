import { describe, expect, it } from "vitest";
import type { ProjectDiffOut, SnapshotRow } from "@/lib/api";
import {
  applyRisks,
  applySnapshotNote,
  canRollbackSnapshot,
  designerHref,
  filterProjectBoard,
  firstCustomModel,
  formatProjectWhen,
  glossaryLines,
  hasProjectSpec,
  isComponentSpec,
  isProjectArchived,
  isProjectApplied,
  modulespecHref,
  projectApplyReviewBlocked,
  projectCanApplyAfterReview,
  projectDiffHeadline,
  projectDiffStats,
  projectSpecSummary,
  projectStatusLabel,
  projectTemplateLabel,
  projectsErrorTitle,
  projectsHeaderDescription,
  projectsHonestyGate,
  projectsJourneyFromState,
  projectsJourneyHint,
  projectsSessionHint,
  projectsSessionState,
  sessionSubmitHint,
  snapshotsForProject,
  sortProjectBoard,
  specModelNames,
  glossaryStrip,
  countLabel,
  type ProjectRow,
} from "./projects-journey";

const draft: ProjectRow = {
  id: "p-draft",
  name: "Visitor log",
  template_id: "library",
  status: "draft",
  lifecycle_status: "active",
  spec_json: {
    models: [
      {
        model: "x_visitor_log",
        fields: [
          { name: "x_name", ttype: "char" },
          { name: "x_host_id", ttype: "many2one" },
        ],
      },
    ],
    views: [{ name: "form" }],
    menus: [{ name: "Visitor log" }],
  },
  created_at: "2026-09-14T10:00:00Z",
};

const applied: ProjectRow = {
  ...draft,
  id: "p-applied",
  status: "applied",
  created_at: "2026-09-13T10:00:00Z",
};

const archived: ProjectRow = {
  ...draft,
  id: "p-archived",
  lifecycle_status: "archived",
  created_at: "2026-09-15T10:00:00Z",
};

const sampleDiff: ProjectDiffOut = {
  ok: true,
  message: "Ready",
  to_create_models: ["x_visitor_log"],
  existing_models: ["res.partner"],
  to_create_fields: ["x_visitor_log.x_name"],
  existing_fields: ["res.partner.name"],
  conflicts: ["x_name type mismatch"],
};

describe("projectsJourneyFromState", () => {
  it("maps browse → inspect → review → apply without mixing ModuleSpec ids", () => {
    expect(projectsJourneyFromState({}).id).toBe("browse");
    expect(projectsJourneyFromState({ selected: true }).id).toBe("inspect");
    expect(projectsJourneyFromState({ selected: true, hasDiff: true }).id).toBe("review");
    expect(projectsJourneyFromState({ busy: "diff", selected: true }).id).toBe("review");
    expect(projectsJourneyFromState({ selected: true, applied: true })).toEqual({
      id: "apply",
      applied: true,
      failed: false,
    });
    expect(projectsJourneyFromState({ busy: "apply", selected: true }).id).toBe("apply");
  });

  it("keeps review current when diff fails", () => {
    expect(projectsJourneyFromState({ failed: true, selected: true, hasDiff: true })).toEqual({
      id: "review",
      failed: true,
      applied: false,
    });
  });
});

describe("projectsJourneyHint", () => {
  it("keeps Completeness / Cert / Autopilot honesty and human promote", () => {
    expect(projectsJourneyHint({ id: "browse" })).toMatch(/hygiene/);
    expect(projectsJourneyHint({ id: "inspect" })).toMatch(/Completeness ≠ Cert ≠ Autopilot/);
    expect(projectsJourneyHint({ id: "review" })).toMatch(/Promote stays human/);
    expect(projectsJourneyHint({ id: "apply" })).toMatch(/Promote stays human/);
    expect(projectsJourneyHint({ id: "apply" })).toMatch(/sandbox/i);
    expect(projectsJourneyHint({ id: "review", failed: true })).toMatch(/Promote stays human/);
  });
});

describe("projectsSessionState", () => {
  it("uses draft / applied / archived like other premium composers", () => {
    expect(projectsSessionState(null)).toBe("draft");
    expect(projectsSessionState(draft)).toBe("draft");
    expect(projectsSessionState(applied)).toBe("applied");
    expect(projectsSessionState(archived)).toBe("archived");
    expect(projectsSessionHint("draft")).toMatch(/until Apply/);
    expect(projectsSessionHint("applied")).toMatch(/snapshot/i);
    expect(projectsSessionHint("archived")).toMatch(/Un-archive/);
  });
});

describe("board helpers", () => {
  it("sorts archived last and filters by lifecycle", () => {
    const sorted = sortProjectBoard([archived, applied, draft]);
    expect(sorted.map((row) => row.id)).toEqual(["p-draft", "p-applied", "p-archived"]);
    expect(filterProjectBoard(sorted, "draft").map((row) => row.id)).toEqual(["p-draft"]);
    expect(filterProjectBoard(sorted, "applied").map((row) => row.id)).toEqual(["p-applied"]);
    expect(filterProjectBoard(sorted, "archived").map((row) => row.id)).toEqual(["p-archived"]);
    expect(projectStatusLabel(draft)).toBe("Draft");
    expect(projectStatusLabel(applied)).toBe("Applied");
    expect(projectStatusLabel(archived)).toBe("Archived");
    expect(projectTemplateLabel("library")).toBe("Library");
    expect(projectTemplateLabel(null)).toBe("Blank");
  });
});

describe("spec helpers", () => {
  it("summarizes models and picks the first custom model for Designer", () => {
    expect(projectSpecSummary(draft.spec_json)).toEqual({
      models: 1,
      fields: 2,
      views: 1,
      menus: 1,
      access: 0,
    });
    expect(specModelNames(draft.spec_json)).toEqual(["x_visitor_log"]);
    expect(firstCustomModel(draft.spec_json)).toBe("x_visitor_log");
    expect(hasProjectSpec(draft.spec_json)).toBe(true);
    expect(hasProjectSpec({})).toBe(false);
    expect(isComponentSpec({ grain: "feature", models: [] })).toBe(true);
    expect(isComponentSpec({ grain: "full_app" })).toBe(false);
  });
});

describe("diff stats", () => {
  it("counts creates, live rows, and conflicts for the review board", () => {
    const stats = projectDiffStats(sampleDiff);
    expect(stats).toEqual({
      createModels: 1,
      createFields: 1,
      existingModels: 1,
      existingFields: 1,
      conflicts: 1,
      toCreate: 2,
      alreadyLive: 2,
    });
    expect(projectDiffHeadline(sampleDiff)).toMatch(/conflict/i);
    expect(
      projectDiffHeadline({
        ...sampleDiff,
        conflicts: [],
      }),
    ).toMatch(/to create/);
    expect(
      projectDiffHeadline({
        ...sampleDiff,
        conflicts: [],
        to_create_models: [],
        to_create_fields: [],
      }),
    ).toMatch(/already exist/);
  });
});

describe("honesty and glossary", () => {
  it("warns on production and keeps sandbox honesty", () => {
    const production = projectsHonestyGate({ writeMode: "production" });
    expect(production.reason).toBe("production");
    expect(production.variant).toBe("danger");
    expect(production.body).toMatch(/Promote stays human/);

    const sandbox = projectsHonestyGate({ writeMode: "standard", localSandboxUrl: true });
    expect(sandbox.reason).toBe("sandbox");
    expect(sandbox.body).toMatch(/Generate UI/);

    expect(projectsHonestyGate({ writeMode: "observer" }).reason).toBe("observer");
    expect(applyRisks().join(" ")).toMatch(/partially recoverable/);
    expect(applySnapshotNote()).toMatch(/partially recoverable/);
    expect(glossaryLines().join(" ")).toMatch(/Promote stays human/);
    expect(glossaryStrip()).toMatch(/Draft · Apply · Promote/);
    expect(countLabel(1, "model")).toBe("1 model");
    expect(countLabel(2, "field")).toBe("2 fields");
    expect(projectsHeaderDescription("Lab 19")).toMatch(/Lab 19/);
    expect(projectsErrorTitle("Diff vs live failed")).toBe("Review vs live failed");
    expect(sessionSubmitHint({ sessionState: "draft", hasDiff: true, canApply: true })).toMatch(
      /Apply on a sandbox/,
    );
    expect(sessionSubmitHint({ sessionState: "draft" })).toMatch(/Review vs live before Apply/);
    expect(projectApplyReviewBlocked(false)).toMatch(/Review vs live before Apply/);
    expect(projectApplyReviewBlocked(true)).toBeNull();
    expect(projectCanApplyAfterReview({ allowed: true, hasDiff: false })).toBe(false);
    expect(projectCanApplyAfterReview({ allowed: true, hasDiff: true })).toBe(true);
    expect(projectCanApplyAfterReview({ allowed: true, hasDiff: true, archived: true })).toBe(false);
  });
});

describe("snapshotsForProject", () => {
  it("prefers model-scoped restore points, then connection model/field snapshots", () => {
    const snapshots: SnapshotRow[] = [
      {
        id: "s1",
        resource_type: "model",
        resource_key: "model:x_visitor_log",
        label: "x_visitor_log",
        reversible: "partial",
        created_at: "2026-09-14T12:00:00Z",
      },
      {
        id: "s2",
        resource_type: "menu",
        resource_key: "menu:1",
        label: "Menus",
        reversible: "yes",
        created_at: "2026-09-14T11:00:00Z",
      },
    ];
    expect(snapshotsForProject(snapshots, draft).map((row) => row.id)).toEqual(["s1"]);
    expect(canRollbackSnapshot("partial")).toBe(true);
    expect(canRollbackSnapshot("none")).toBe(false);
    expect(modulespecHref("c1", "p-draft")).toBe("/connections/c1/modulespec?project=p-draft");
    expect(designerHref("c1", "x_visitor_log")).toBe(
      "/connections/c1/designer?model=x_visitor_log",
    );
    expect(isProjectArchived(archived)).toBe(true);
    expect(isProjectApplied(applied)).toBe(true);
    expect(formatProjectWhen("not-a-date")).toBe("not-a-date");
  });
});
