/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FieldList } from "./FieldList";
import type { FieldRow } from "@/lib/api";

afterEach(() => cleanup());

const fields: FieldRow[] = [
  {
    id: 1,
    name: "x_note",
    field_description: "Note",
    ttype: "char",
    required: false,
    readonly: false,
    relation: null,
    state: "manual",
  },
  {
    id: 2,
    name: "name",
    field_description: "Name",
    ttype: "char",
    required: true,
    readonly: false,
    relation: null,
    state: "base",
  },
];

describe("FieldList", () => {
  it("distinguishes hide-in-view from remove-from-model", () => {
    const onRemove = vi.fn();
    const onSelect = vi.fn();
    render(
      <FieldList
        fields={fields}
        selectedFieldId={null}
        query=""
        onQueryChange={vi.fn()}
        onSelect={onSelect}
        onCreate={vi.fn()}
        onRemoveFromModel={onRemove}
        designerHref="/connections/c1/designer?model=x_ticket"
      />,
    );
    const hide = screen.getAllByRole("link", { name: "Hide in View Designer" });
    expect(hide[0].getAttribute("href")).toContain("/designer");
    fireEvent.click(screen.getByTestId("builder-remove-field-x_note"));
    expect(onRemove).toHaveBeenCalledWith(fields[0]);
    expect(screen.queryByTestId("builder-remove-field-name")).not.toBeInTheDocument();
  });
});
