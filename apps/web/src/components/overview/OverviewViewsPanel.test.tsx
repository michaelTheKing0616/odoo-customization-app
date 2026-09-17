import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { OverviewViewsPanel } from "@/components/overview/OverviewViewsPanel";
import type { ViewRow } from "@/lib/api";

afterEach(() => cleanup());

const views: ViewRow[] = [
  {
    id: 1847,
    name: "res.partner.form",
    model: "res.partner",
    type: "form",
    arch: "<form><field name=\"name\"/></form>",
    priority: 16,
  },
  {
    id: 1902,
    name: "res.partner.tree",
    model: "res.partner",
    type: "list",
    arch: "<list><field name=\"name\"/></list>",
    priority: 8,
  },
  {
    id: 2001,
    name: "res.partner.kanban",
    model: "res.partner",
    type: "kanban",
    arch: "<kanban/>",
  },
];

describe("OverviewViewsPanel", () => {
  it("shows helper copy and groups by type with arch collapsed", () => {
    render(<OverviewViewsPanel model="res.partner" views={views} />);
    expect(screen.getByTestId("overview-views-helper")).toHaveTextContent(
      /Showing 3 views for res\.partner/,
    );
    expect(screen.getByTestId("overview-views-helper")).toHaveTextContent(/database ids/);
    expect(screen.getByTestId("overview-views-group-form")).toBeInTheDocument();
    expect(screen.getByTestId("overview-views-group-list")).toBeInTheDocument();
    expect(screen.getByTestId("overview-views-group-kanban")).toBeInTheDocument();

    const idHint = screen.getByTitle(
      "Odoo ir.ui.view database id (not a sequence index)",
    );
    expect(idHint).toHaveTextContent("id 1847");
    expect(screen.getByText("priority 16")).toBeInTheDocument();

    expect(screen.queryByTestId("code-block")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("res.partner.form"));
    expect(screen.getByTestId("code-block")).toBeInTheDocument();
    expect(screen.getByText("Hide arch")).toBeInTheDocument();
  });
});
