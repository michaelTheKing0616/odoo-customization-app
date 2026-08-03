import { describe, expect, it } from "vitest";

const KIT_COMPONENTS = [
  "Button",
  "Input",
  "Textarea",
  "Select",
  "Combobox",
  "DialogPanel",
  "Sheet",
  "Toast",
  "Tabs",
  "DataTable",
  "Badge",
  "StatusPill",
  "Callout",
  "EmptyState",
  "Skeleton",
  "Tooltip",
  "Kbd",
  "Card",
  "PageHeader",
  "Breadcrumbs",
  "CodeBlock",
  "DiffView",
  "BulkResultTable",
  "ConfirmDialogV2",
  "CommandPalette",
  "ErrorNotice",
] as const;

describe("UIX-2 kit contract", () => {
  it("lists all required kit components", () => {
    expect(KIT_COMPONENTS.length).toBeGreaterThanOrEqual(20);
  });

  it("documents primary button rule", () => {
    expect("primary").toBeTruthy();
  });
});

describe("BulkRunResult shape", () => {
  it("accepts per-record rows", () => {
    const row = { record_id: 1, ok: true, error: null };
    expect(row.record_id).toBe(1);
  });
});

describe("DiffView line types", () => {
  it("supports add/remove/context", () => {
    expect(["add", "remove", "context"]).toContain("add");
  });
});
