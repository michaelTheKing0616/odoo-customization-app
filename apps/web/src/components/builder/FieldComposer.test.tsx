/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FieldComposer } from "./FieldComposer";
import { defaultFieldForm } from "@/lib/builderForm";
import type { Connection } from "@/lib/api";

afterEach(() => cleanup());

function conn(major: number, supported: string[]): Connection {
  return {
    id: "mock",
    name: "Mock",
    url: "http://127.0.0.1:8069",
    db_name: "odoo_dev",
    username: "admin",
    server_version: `${major}.0`,
    write_mode: "standard",
    created_at: null,
    updated_at: null,
    capabilities: {
      major,
      ga: major >= 17,
      edition: "community",
      server_version: `${major}.0`,
      message: `mock ${major}`,
      supported,
      unsupported: supported.includes("view_inject_inherit")
        ? []
        : [
            {
              id: "view_inject_inherit",
              label: "View inject inherit",
              reason: "Unavailable on this Odoo version",
            },
          ],
    },
  };
}

describe("FieldComposer", () => {
  it("gates monetary currency_field on Odoo 16", () => {
    const form = { ...defaultFieldForm("x_ticket"), ttype: "monetary" };
    render(
      <FieldComposer
        connectionId="c1"
        connection={conn(16, [])}
        form={form}
        mode="create"
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        widgetOptions={[]}
        relatedPaths={[]}
      />,
    );
    expect(screen.getByTestId("builder-currency-gate")).toHaveTextContent("currency_field");
  });

  it("gates view inject when inherit is unsupported", () => {
    render(
      <FieldComposer
        connectionId="c1"
        connection={conn(16, [])}
        form={defaultFieldForm("x_ticket")}
        mode="create"
        onChange={vi.fn()}
        onSubmit={vi.fn()}
        widgetOptions={[]}
        relatedPaths={[]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Related path, widget, and view inject/i }));
    expect(screen.getByTestId("builder-inject-views")).toBeDisabled();
    expect(screen.getByTestId("builder-inject-gate")).toBeTruthy();
  });
});
