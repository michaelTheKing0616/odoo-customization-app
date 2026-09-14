import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FormCanvas } from "./FormCanvas";

describe("FormCanvas designer DnD surface", () => {
  it("renders statusbar stages, two-column groups, and notebook tab switch", () => {
    render(
      <FormCanvas
        title="Ticket"
        statusbar="x_status"
        statusbarVisible="new,in_progress,done"
        groupLayout="two-column"
        headerButtons={[{ id: "c", string: "Confirm", variant: "primary" }]}
        smartButtons={[{ id: "s", string: "Tasks", count: 4 }]}
        groups={[
          {
            id: "g1",
            string: "Identity",
            fields: [{ id: "f1", name: "x_name", string: "Subject" }],
          },
          {
            id: "g2",
            string: "Details",
            fields: [{ id: "f2", name: "x_priority", string: "Priority" }],
          },
        ]}
        notebooks={[
          {
            id: "nb1",
            pages: [
              {
                id: "p1",
                string: "Lines",
                fields: [{ id: "lf1", name: "x_qty", string: "Qty" }],
              },
              {
                id: "p2",
                string: "Notes",
                fields: [{ id: "nf1", name: "x_notes", string: "Notes" }],
              },
            ],
          },
        ]}
      />,
    );

    expect(screen.getByTestId("form-canvas")).toBeTruthy();
    expect(screen.getByTestId("odoo-statusbar")).toBeTruthy();
    expect(screen.getByText("new")).toBeTruthy();
    expect(screen.getByText("Confirm")).toBeTruthy();
    expect(screen.getByTestId("odoo-button-box")).toBeTruthy();
    expect(screen.getByText("Qty")).toBeTruthy();
    expect(screen.queryByText("x_notes")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Notes" }));
    expect(screen.getByText("x_notes")).toBeTruthy();
    expect(screen.queryByText("x_qty")).toBeNull();
  });

  it("keeps keyboard reorder callback contract", () => {
    const moves: Array<{ id: string; dir: -1 | 1 }> = [];
    render(
      <FormCanvas
        title="Ticket"
        groups={[
          {
            id: "g1",
            string: "Identity",
            fields: [
              { id: "f1", name: "x_name", string: "Subject" },
              { id: "f2", name: "x_code", string: "Code" },
            ],
          },
        ]}
        selectedFieldId="f1"
        onMoveField={(id, dir) => moves.push({ id, dir })}
        showChatter={false}
      />,
    );
    fireEvent.keyDown(window, { key: "ArrowDown" });
    expect(moves).toEqual([{ id: "f1", dir: 1 }]);
  });
});
