/** @vitest-environment jsdom */
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { BuilderModelPreview } from "./BuilderModelPreview";
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
  {
    id: 2,
    name: "x_partner_id",
    field_description: "Customer",
    ttype: "many2one",
    required: false,
    readonly: false,
    relation: "res.partner",
    state: "manual",
  },
];

describe("BuilderModelPreview", () => {
  it("renders form and list teasers plus designer and automations links", () => {
    render(
      <BuilderModelPreview
        connectionId="conn-1"
        model="x_demo"
        modelLabel="Demo"
        fields={fields}
        enableMailThread
      />,
    );
    expect(screen.getByTestId("builder-model-preview")).toBeTruthy();
    expect(screen.getByTestId("odoo-form-view")).toBeTruthy();
    expect(screen.getByTestId("odoo-list-view")).toBeTruthy();
    expect(screen.getByTestId("odoo-chatter-stub")).toBeTruthy();
    const link = screen.getByRole("link", { name: /Customize layout in View Designer/i });
    expect(link.getAttribute("href")).toContain("/connections/conn-1/designer");
    expect(link.getAttribute("href")).toContain("model=x_demo");
    const autos = screen.getByRole("link", { name: /Automations for this model/i });
    expect(autos.getAttribute("href")).toContain("/connections/conn-1/automations");
  });

  it("shows an honest empty teaser when the model has no fields yet", () => {
    render(
      <BuilderModelPreview
        connectionId="conn-1"
        model="x_demo"
        modelLabel="Demo"
        fields={[]}
      />,
    );
    expect(screen.getByText("Layout preview waits on fields")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Open View Designer/i }).getAttribute("href")).toContain(
      "model=x_demo",
    );
  });
});
