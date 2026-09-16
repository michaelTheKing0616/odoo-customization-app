/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DesignerFieldInspector,
  DesignerFieldInspectorEmpty,
} from "./DesignerFieldInspector";
import { TooltipProvider } from "@/components/ui/Tooltip";
import type { FieldRow, RelatedPathOption } from "@/lib/api";

afterEach(() => {
  cleanup();
});

const META: FieldRow = {
  id: 12,
  name: "x_email",
  field_description: "Work email",
  ttype: "char",
  required: false,
  readonly: false,
  relation: null,
  state: "manual",
  related: "partner_id.email",
  help: "ORM help",
};

const RELATED_PATHS: RelatedPathOption[] = [
  { path: "partner_id.email", label: "Customer → Email", ttype: "char" },
  { path: "partner_id.phone", label: "Customer → Phone", ttype: "char" },
];

function openInspectorSection(title: string) {
  const btn = screen.getByRole("button", { name: title });
  if (btn.getAttribute("aria-expanded") !== "true") {
    fireEvent.click(btn);
  }
}

function renderInspector(
  overrides: Partial<React.ComponentProps<typeof DesignerFieldInspector>> = {},
) {
  const onChange = vi.fn();
  const onRemove = vi.fn();
  const onAdd = vi.fn();
  render(
    <TooltipProvider>
      <DesignerFieldInspector
        field={{
          name: "x_email",
          string: "Work email",
          widget: "email",
          help: "Shown on hover",
          placeholder: "name@company.com",
          class_name: "oe_inline",
          groups: "base.group_user",
        }}
        fieldMeta={META}
        widgetOptions={[
          { id: "email", label: "Email" },
          { id: "phone", label: "Phone" },
        ]}
        widgetAdvanced={false}
        onWidgetAdvancedChange={vi.fn()}
        onChange={onChange}
        groups={[{ id: 1, name: "Internal User", full_name: "Internal User", share: false }]}
        groupsState="ready"
        relatedPaths={RELATED_PATHS}
        relatedState="ready"
        fieldsOnModel={[META]}
        viewFieldNames={["x_email"]}
        onAddRelatedField={onAdd}
        onRemoveFromView={onRemove}
        {...overrides}
      />
    </TooltipProvider>,
  );
  return { onChange, onRemove, onAdd };
}

describe("DesignerFieldInspector", () => {
  it("exposes display chrome and view-only remove copy", () => {
    const { onChange, onRemove } = renderInspector();
    expect(screen.getByTestId("designer-field-inspector")).toBeInTheDocument();
    expect(screen.getByTestId("inspector-field-name")).toHaveTextContent("x_email");
    expect(screen.getByText("Related")).toBeInTheDocument();
    expect(screen.getByTestId("inspector-related-path")).toHaveTextContent(
      "partner_id.email",
    );

    openInspectorSection("Layout");
    expect(screen.getByTestId("inspector-help")).toHaveValue("Shown on hover");
    expect(screen.getByTestId("inspector-placeholder")).toHaveValue("name@company.com");
    expect(screen.getByTestId("inspector-class")).toHaveValue("oe_inline");

    fireEvent.change(screen.getByTestId("inspector-label"), {
      target: { value: "Office email" },
    });
    expect(onChange).toHaveBeenCalledWith({ string: "Office email" });

    openInspectorSection("Inherit");
    expect(screen.getByTestId("inspector-remove-copy")).toHaveTextContent(
      "does not delete the database column",
    );
    fireEvent.click(screen.getByTestId("inspector-remove"));
    expect(onRemove).toHaveBeenCalled();
  });

  it("uses Off | Always | When for required, readonly, and invisible", () => {
    const { onChange } = renderInspector();
    openInspectorSection("Attributes");
    fireEvent.click(screen.getByTestId("inspector-modifier-required-always"));
    expect(onChange).toHaveBeenCalledWith({ required: true });
    fireEvent.click(screen.getByTestId("inspector-modifier-readonly-off"));
    expect(onChange).toHaveBeenCalledWith({ readonly: undefined });
    fireEvent.click(screen.getByTestId("inspector-modifier-invisible-always"));
    expect(onChange).toHaveBeenCalledWith({ invisible: true });
  });

  it("adds group xml ids from presets", () => {
    const { onChange } = renderInspector({
      field: { name: "x_email", groups: undefined },
    });
    openInspectorSection("Attributes");
    fireEvent.click(screen.getByRole("button", { name: "Group visibility" }));
    const select = screen.getByLabelText("Add a common group");
    fireEvent.change(select, { target: { value: "base.group_system" } });
    expect(onChange).toHaveBeenCalledWith({ groups: "base.group_system" });
  });

  it("shows image size presets instead of raw JSON-only", () => {
    renderInspector({
      field: { name: "x_photo", widget: "image", options: '{"size": [128, 128]}' },
      fieldMeta: { ...META, name: "x_photo", ttype: "binary", related: null },
      widgetOptions: [{ id: "image", label: "Image" }],
    });
    openInspectorSection("Attributes");
    expect(screen.getByTestId("inspector-widget-options")).toHaveValue(
      '{"size": [128, 128]}',
    );
  });

  it("empty state reinforces remove-from-view vs delete column", () => {
    render(<DesignerFieldInspectorEmpty />);
    expect(screen.getByTestId("designer-field-inspector-empty")).toHaveTextContent(
      "does not delete the column",
    );
  });
});

describe("DesignerFieldInspector accordion", () => {
  it("opens Selection by default; Layout Attributes Inherit collapsed", () => {
    renderInspector();
    expect(screen.getByTestId("inspector-section-selection").querySelector("[aria-expanded=\"true\"]")).toBeTruthy();
    expect(screen.getByTestId("inspector-section-layout").querySelector("[aria-expanded=\"true\"]")).toBeNull();
    expect(screen.getByTestId("inspector-section-attributes").querySelector("[aria-expanded=\"true\"]")).toBeNull();
    expect(screen.getByTestId("inspector-section-inherit").querySelector("[aria-expanded=\"true\"]")).toBeNull();
    expect(screen.getByTestId("inspector-label")).toBeInTheDocument();
  });
});
