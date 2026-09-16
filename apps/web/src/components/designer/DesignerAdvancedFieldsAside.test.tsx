import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { DesignerAdvancedFieldsAside } from "@/components/designer/DesignerAdvancedFieldsAside";
import type { Connection } from "@/lib/api";

const connection = {
  id: "c1",
  name: "Demo",
  url: "https://example.odoo.com",
  db_name: "db",
  username: "admin",
  server_version: "17.0",
  write_mode: "standard",
  created_at: null,
  updated_at: null,
  capabilities: {
    ga: true,
    edition: "community",
    hosting_hint: "unknown",
    major: 17,
    supported: ["view_inject_inherit", "view_inject_mutate"],
    unsupported: [],
    message: "",
  },
} as Connection;

const baseProps = {
  connection,
  viewType: "form",
  fields: [] as [],
  newFieldName: "x_test",
  setNewFieldName: vi.fn(),
  newFieldLabel: "Test",
  setNewFieldLabel: vi.fn(),
  newFieldType: "char",
  setNewFieldType: vi.fn(),
  injectStrategy: "inherit" as const,
  setInjectStrategy: vi.fn(),
  confirmPhrase: "I understand the risks",
  setConfirmPhrase: vi.fn(),
  busy: false,
  setDragField: vi.fn(),
  addListColumn: vi.fn(),
  addSearchField: vi.fn(),
  addKanbanField: vi.fn(),
  nicheWidgets: [] as [],
  colorPalette: [] as string[],
  onCreateAndInject: vi.fn(),
  onPickNicheWidget: vi.fn(),
};

function createInjectButton() {
  return screen.getByText("Create + inject");
}

describe("DesignerAdvancedFieldsAside", () => {
  it("disables create+inject when model is empty (regression: model prop required)", () => {
    const { container } = render(<DesignerAdvancedFieldsAside {...baseProps} model="" />);
    expect(within(container).getByText("Create + inject")).toBeDisabled();
  });

  it("enables create+inject when model and x_ field name are set", () => {
    const { container } = render(
      <DesignerAdvancedFieldsAside {...baseProps} model="x_demo.model" />,
    );
    expect(within(container).getByText("Create + inject")).not.toBeDisabled();
  });
});
