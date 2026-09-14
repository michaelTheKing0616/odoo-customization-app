/** @vitest-environment jsdom */
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AutomationActionKindSelect } from "@/components/AutomationActionKindSelect";
import type { Connection } from "@/lib/api";

afterEach(() => cleanup());

function conn(supported: string[]): Connection {
  return {
    id: "c1",
    name: "Test",
    url: "http://127.0.0.1:8069",
    db_name: "odoo_dev",
    username: "admin",
    server_version: "16.0",
    write_mode: "standard",
    created_at: null,
    updated_at: null,
    capabilities: {
      major: 16,
      edition: "community",
      server_version: "16.0",
      ga: false,
      message: "experimental",
      supported,
      unsupported: [],
    },
  };
}

describe("AutomationActionKindSelect", () => {
  it("keeps update_field and related_write greyed out without update_path caps", () => {
    render(
      <AutomationActionKindSelect
        connection={conn(["object_create_crud_model"])}
        value="create_activity"
        onChange={() => undefined}
      />,
    );
    const select = screen.getByTestId("automation-action-kind");
    expect(select.querySelector('option[value="update_field"]')).toHaveAttribute("disabled");
    expect(select.querySelector('option[value="related_write"]')).toHaveAttribute("disabled");
    expect(select.querySelector('option[value="create_activity"]')).not.toHaveAttribute(
      "disabled",
    );
    expect(select.querySelector('optgroup[label="Safe"]')).toBeTruthy();
    expect(select.querySelector('optgroup[label="Option A"]')).toBeTruthy();
  });
});
