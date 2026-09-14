/** @vitest-environment jsdom */
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ModelDetail } from "./ModelDetail";
import type { FieldRow } from "@/lib/api";

afterEach(() => cleanup());

const fields: FieldRow[] = [
  {
    id: 1,
    name: "x_name",
    field_description: "Name",
    ttype: "char",
    required: true,
    readonly: false,
    relation: null,
    state: "manual",
  },
];

describe("ModelDetail", () => {
  it("shows success path to View Designer and Automations", () => {
    render(
      <ModelDetail
        connectionId="c1"
        model="x_ticket"
        modelLabel="Ticket"
        customRow={{
          id: 3,
          model: "x_ticket",
          name: "Ticket",
          state: "manual",
          transient: false,
        }}
        fields={fields}
        fieldQuery=""
        selectedFieldId={null}
        justCreated
        onFieldQueryChange={vi.fn()}
        onSelectField={vi.fn()}
        onNewField={vi.fn()}
        onRemoveField={vi.fn()}
      />,
    );
    expect(screen.getByTestId("builder-model-success")).toBeTruthy();
    expect(screen.getByTestId("builder-success-designer").getAttribute("href")).toContain(
      "/connections/c1/designer?model=x_ticket",
    );
    expect(screen.getByTestId("builder-designer-link").getAttribute("href")).toContain(
      "model=x_ticket",
    );
    expect(screen.getByTestId("builder-automations-link").getAttribute("href")).toContain(
      "/connections/c1/automations?model=x_ticket",
    );
  });
});
