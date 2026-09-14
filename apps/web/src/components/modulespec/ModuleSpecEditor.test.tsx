/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ModuleSpecEditor } from "@/components/ModuleSpecEditor";
import type { ModuleSpecDoc } from "@/lib/modulespec-types";

afterEach(() => cleanup());

const spec: ModuleSpecDoc = {
  technical_name: "visitor_log",
  display_name: "Visitor log",
  models: [
    {
      model: "x_visitor_log",
      description: "Visitor log",
      fields: [{ name: "x_name", ttype: "char", string: "Name", required: true }],
    },
  ],
  views: [{ name: "x_visitor_log.form", model: "x_visitor_log", type: "form", arch: "<form/>" }],
  menus: [{ name: "Visitor log" }],
  access_rules: [{ name: "User", model: "model_x_visitor_log", perm_read: 1 }],
};

describe("ModuleSpecEditor", () => {
  it("treats JSON as a secondary disclosure, not a peer tab", () => {
    render(<ModuleSpecEditor value={spec} onChange={vi.fn()} />);
    expect(screen.getByTestId("modulespec-editor")).toBeTruthy();
    expect(screen.getByRole("tab", { name: /Models/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("modulespec-models")).toBeTruthy();
    expect(screen.queryByRole("tab", { name: /JSON/ })).toBeNull();
    expect(screen.getByTestId("modulespec-json-disclosure")).toBeTruthy();
    expect(screen.getByText(/Raw JSON escape hatch/)).toBeTruthy();
  });

  it("opens views, menus, and security as structured sections", () => {
    render(<ModuleSpecEditor value={spec} onChange={vi.fn()} />);
    fireEvent.click(screen.getByRole("tab", { name: /Views/ }));
    expect(screen.getByTestId("modulespec-views")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: /Menus/ }));
    expect(screen.getByTestId("modulespec-menus")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: /Security/ }));
    expect(screen.getByTestId("modulespec-security")).toBeTruthy();
  });
});
